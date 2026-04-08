from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import feedparser
import httpx
import google.generativeai as genai
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates
from groq import Groq
from openai import OpenAI
from pydantic import BaseModel, Field

from ..core.config import settings
from ..core.storage import read_json, utc_now_iso, write_json


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


Provider = Literal["openai", "groq", "gemini"]


DEFAULT_FEEDS = [
    "https://www.searchenginejournal.com/feed/",
    "https://www.socialmediatoday.com/feeds/news/",
    "https://hnrss.org/newest",
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(text: str) -> str:
    value = text.lower().strip()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_-]+", "-", value, flags=re.UNICODE).strip("-")
    return value[:80] if value else uuid.uuid4().hex[:10]


def _get_ai_clients() -> Tuple[Optional[OpenAI], Optional[Groq], Optional[Any]]:
    client_openai = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
    client_groq = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
    if settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        client_gemini = genai.GenerativeModel("gemini-pro")
    else:
        client_gemini = None
    return client_openai, client_groq, client_gemini


def _ai_generate(provider: Provider, prompt: str) -> str:
    client_openai, client_groq, client_gemini = _get_ai_clients()

    if provider == "gemini":
        if not client_gemini:
            raise HTTPException(status_code=400, detail="Gemini no está configurado.")
        result = client_gemini.generate_content(prompt)
        return (result.text or "").strip()

    if provider == "groq":
        if not client_groq:
            raise HTTPException(status_code=400, detail="Groq no está configurado.")
        result = client_groq.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1400,
        )
        return (result.choices[0].message.content or "").strip()

    if not client_openai:
        raise HTTPException(status_code=400, detail="OpenAI no está configurado.")
    result = client_openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1400,
    )
    return (result.choices[0].message.content or "").strip()


def _posts_store() -> Dict[str, Any]:
    data = read_json("posts", default={})
    return data if isinstance(data, dict) else {}


def _topics_store() -> Dict[str, Any]:
    data = read_json("topics", default={})
    return data if isinstance(data, dict) else {}


def _analytics_store() -> Dict[str, Any]:
    data = read_json("analytics", default={"pageviews": {}, "referrers": {}})
    return data if isinstance(data, dict) else {"pageviews": {}, "referrers": {}}


def track_pageview(path: str, referrer: Optional[str]) -> None:
    data = _analytics_store()
    pageviews = data.get("pageviews") if isinstance(data.get("pageviews"), dict) else {}
    pageviews[path] = int(pageviews.get(path, 0)) + 1
    data["pageviews"] = pageviews

    if referrer:
        referrers = data.get("referrers") if isinstance(data.get("referrers"), dict) else {}
        referrers[referrer] = int(referrers.get(referrer, 0)) + 1
        data["referrers"] = referrers

    write_json("analytics", data)


def list_published_posts() -> List[Dict[str, Any]]:
    posts = _posts_store()
    items = [p for p in posts.values() if isinstance(p, dict) and p.get("status") == "published"]
    items.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return items


def find_post_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    posts = _posts_store()
    for item in posts.values():
        if isinstance(item, dict) and item.get("slug") == slug and item.get("status") == "published":
            return item
    return None


class FeedIngestRequest(BaseModel):
    rss_urls: List[str] = Field(default_factory=lambda: DEFAULT_FEEDS)
    max_items: int = 40


class GeneratePostRequest(BaseModel):
    provider: Provider = "gemini"
    max_candidates: int = 25
    niche: str = "marketing digital, automatización, IA para negocios"
    brand: str = "TrafficForge AI"


class PublishRequest(BaseModel):
    post_id: str


@router.get("/organic/health")
async def health():
    posts = _posts_store()
    topics = _topics_store()
    analytics = _analytics_store()
    return {
        "posts": len(posts),
        "topics": len(topics),
        "pageviews": len((analytics.get("pageviews") or {})),
        "status": "ok",
    }


@router.post("/organic/ingest-feeds")
async def ingest_feeds(payload: FeedIngestRequest):
    topics = _topics_store()
    created = 0

    async with httpx.AsyncClient(timeout=20) as client:
        for url in payload.rss_urls[:20]:
            try:
                resp = await client.get(url, headers={"User-Agent": "TrafficForgeAI/1.0"})
                parsed = feedparser.parse(resp.text)
                for entry in parsed.entries[: payload.max_items]:
                    title = (getattr(entry, "title", "") or "").strip()
                    link = (getattr(entry, "link", "") or "").strip()
                    if not title:
                        continue
                    topic_id = _slugify(f"{title}-{link}")[:60]
                    if topic_id in topics:
                        continue
                    topics[topic_id] = {
                        "id": topic_id,
                        "title": title,
                        "link": link,
                        "source": url,
                        "created_at": utc_now_iso(),
                        "used": False,
                    }
                    created += 1
            except Exception:
                continue

    write_json("topics", topics)
    return {"created": created, "total_topics": len(topics)}


def _pick_topic(max_candidates: int, niche: str) -> Optional[Dict[str, Any]]:
    topics = _topics_store()
    candidates = [t for t in topics.values() if isinstance(t, dict) and not t.get("used")]
    candidates = candidates[: max_candidates]
    if not candidates:
        return None

    needle = niche.lower()
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for t in candidates:
        title = str(t.get("title") or "").lower()
        score = 0
        for w in needle.split(","):
            w = w.strip()
            if w and w in title:
                score += 1
        scored.append((score, t))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else candidates[0]


def _build_article_prompt(brand: str, niche: str, topic_title: str, topic_link: str) -> str:
    landing = settings.LANDING_PAGE_URL
    return f"""
Eres un redactor SEO senior y estratega de crecimiento orgánico.

Objetivo: crear un artículo que atraiga tráfico orgánico y convierta sin spam.

Marca: {brand}
Nicho: {niche}
Tema (inspiración): {topic_title}
Fuente: {topic_link}

Requisitos:
- Escribe en español neutral.
- No menciones la fuente.
- Incluye: 1 H1, 5 H2, listas, ejemplos, y un CTA suave al final.
- El CTA debe invitar a probar {brand} para automatizar marketing (sin promesas exageradas).
- El CTA debe incluir un enlace HTML clickable a: {landing}
- Devuelve SOLO HTML válido (sin markdown, sin ```).

Genera el artículo ahora.
""".strip()


def _build_social_prompt(brand: str, topic_title: str, article_html: str) -> str:
    return f"""
Actúa como estratega de contenido para redes sociales.

Basado en este artículo HTML (resumido): {article_html[:1200]}

Devuelve un JSON con estas claves exactas:
- tiktok_script (45-60s)
- reels_caption (máx 2200 chars)
- carousel_outline (7 slides)
- hashtags (lista de 12)

Tema: {topic_title}
Marca: {brand}
""".strip()


@router.post("/organic/generate-post")
async def generate_post(payload: GeneratePostRequest):
    client_openai, client_groq, client_gemini = _get_ai_clients()
    if not client_openai and not client_groq and not client_gemini:
        raise HTTPException(status_code=503, detail="IA no configurada. Añade OpenAI, Groq o Gemini en el .env")

    topic = _pick_topic(max_candidates=payload.max_candidates, niche=payload.niche)
    if not topic:
        raise HTTPException(status_code=404, detail="No hay topics disponibles. Ejecuta ingest-feeds.")

    prompt = _build_article_prompt(
        brand=payload.brand,
        niche=payload.niche,
        topic_title=str(topic.get("title") or ""),
        topic_link=str(topic.get("link") or ""),
    )
    article_html = _ai_generate(payload.provider, prompt)
    title = str(topic.get("title") or payload.brand).strip()
    slug = _slugify(title)

    social_prompt = _build_social_prompt(payload.brand, title, article_html)
    social_raw = _ai_generate(payload.provider, social_prompt)

    post_id = uuid.uuid4().hex
    post = {
        "id": post_id,
        "title": title,
        "slug": slug,
        "status": "draft",
        "provider": payload.provider,
        "niche": payload.niche,
        "created_at": utc_now_iso(),
        "published_at": None,
        "content_html": article_html,
        "social_assets_raw": social_raw,
    }

    posts = _posts_store()
    posts[post_id] = post
    write_json("posts", posts)

    topics = _topics_store()
    topic_id = str(topic.get("id") or "")
    if topic_id and topic_id in topics and isinstance(topics[topic_id], dict):
        topics[topic_id]["used"] = True
        topics[topic_id]["used_at"] = utc_now_iso()
        topics[topic_id]["post_id"] = post_id
        write_json("topics", topics)

    return {"post_id": post_id, "slug": slug, "status": "draft"}


@router.post("/organic/publish-post")
async def publish_post(payload: PublishRequest):
    posts = _posts_store()
    post = posts.get(payload.post_id)
    if not isinstance(post, dict):
        raise HTTPException(status_code=404, detail="Post no encontrado.")

    post["status"] = "published"
    post["published_at"] = utc_now_iso()
    posts[payload.post_id] = post
    write_json("posts", posts)

    return {"status": "published", "url": f"/blog/{post.get('slug')}"}


async def run_daily_pipeline() -> None:
    topics = _topics_store()
    if len(topics) < 10:
        try:
            await ingest_feeds(FeedIngestRequest(), current_user={"plan": "pro"})
        except Exception:
            return

    today = _now_utc().date().isoformat()
    posts = _posts_store()
    already = any(
        isinstance(p, dict)
        and p.get("status") == "published"
        and str(p.get("published_at") or "").startswith(today)
        for p in posts.values()
    )
    if already:
        return

    generated = await generate_post(GeneratePostRequest(provider="gemini"), current_user={"plan": "pro"})
    post_id = generated.get("post_id")
    if post_id:
        await publish_post(PublishRequest(post_id=post_id), current_user={"plan": "pro"})


@router.get("/blog", response_class=HTMLResponse, include_in_schema=False)
async def blog_index(request: Request):
    posts = list_published_posts()
    track_pageview("/blog", request.headers.get("referer"))
    template = templates.env.get_template("blog_index.html")
    html = template.render(request=request, posts=posts)
    return HTMLResponse(content=html)


@router.get("/blog/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def blog_post(slug: str, request: Request):
    post = find_post_by_slug(slug)
    if not post:
        raise HTTPException(status_code=404, detail="Artículo no encontrado.")
    track_pageview(f"/blog/{slug}", request.headers.get("referer"))
    template = templates.env.get_template("blog_post.html")
    html = template.render(request=request, post=post)
    return HTMLResponse(content=html)


@router.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots():
    return "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n"


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    posts = list_published_posts()
    urls = ["<url><loc>/</loc></url>", "<url><loc>/blog</loc></url>"]
    for p in posts[:2000]:
        slug = p.get("slug")
        if slug:
            urls.append(f"<url><loc>/blog/{slug}</loc></url>")
    body = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
    body += "\n".join(urls)
    body += "\n</urlset>\n"
    return Response(content=body, media_type="application/xml")
