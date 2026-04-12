from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import feedparser
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates
from groq import Groq
from openai import OpenAI
from pydantic import BaseModel, Field

from ..core.config import has_real_secret, settings
from ..core.storage import utc_now_iso
from ..core import repo


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

try:
    from google import genai as google_genai
except Exception:
    google_genai = None


Provider = Literal["openai", "groq", "gemini"]


DEFAULT_FEEDS = [
    "https://www.searchenginejournal.com/feed/",
    "https://www.socialmediatoday.com/feeds/news/",
    "https://hnrss.org/newest",
]


def _strip_html_to_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _meta_description_from_html(html: str, limit: int = 160) -> str:
    text = _strip_html_to_text(html)
    if len(text) <= limit:
        return text
    cut = text[: limit + 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.strip()


def _effective_public_base_url(request: Request) -> str:
    if settings.PUBLIC_BASE_URL:
        return settings.PUBLIC_BASE_URL.rstrip("/")
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",")[0].strip()
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc).split(",")[0].strip()
    if not host:
        return str(request.base_url).rstrip("/")
    if proto not in ("http", "https"):
        proto = "https"
    return f"{proto}://{host}"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(text: str) -> str:
    value = text.lower().strip()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_-]+", "-", value, flags=re.UNICODE).strip("-")
    return value[:80] if value else uuid.uuid4().hex[:10]


def _get_ai_clients() -> Tuple[Optional[OpenAI], Optional[Groq], Optional[Any]]:
    client_openai = OpenAI(api_key=settings.OPENAI_API_KEY) if has_real_secret(settings.OPENAI_API_KEY) else None
    client_groq = Groq(api_key=settings.GROQ_API_KEY) if has_real_secret(settings.GROQ_API_KEY) else None
    client_gemini = (
        google_genai.Client(api_key=settings.GEMINI_API_KEY)
        if has_real_secret(settings.GEMINI_API_KEY) and google_genai
        else None
    )
    return client_openai, client_groq, client_gemini


def _gemini_text(result) -> str:
    text = getattr(result, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    try:
        return str(result.candidates[0].content.parts[0].text).strip()
    except Exception:
        return str(result).strip()


def _list_gemini_models(client: Any) -> List[str]:
    try:
        res = client.models.list()
    except Exception:
        return []
    names: List[str] = []
    try:
        for m in res:
            name = getattr(m, "name", None) or getattr(m, "model", None)
            if isinstance(name, str) and name:
                if name.startswith("models/"):
                    name = name.split("/", 1)[1]
                names.append(name)
    except Exception:
        return []
    return names


def _pick_gemini_models(client: Any) -> List[str]:
    forced = settings.GEMINI_MODEL or settings.GEMINI_MODELO
    if forced:
        return [forced]
    preferred = [
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
        "gemini-pro-latest",
    ]
    available = _list_gemini_models(client)
    available_set = set(available)
    candidates = [m for m in preferred if m in available_set]
    if candidates:
        return candidates
    if available:
        return available[:3]
    return preferred[:1]


def _ai_generate(provider: Provider, prompt: str) -> str:
    client_openai, client_groq, client_gemini = _get_ai_clients()

    if provider == "gemini":
        if not client_gemini:
            raise HTTPException(status_code=400, detail="Gemini no está configurado.")
        last_error: Optional[str] = None
        for model_name in _pick_gemini_models(client_gemini):
            try:
                result = client_gemini.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = _gemini_text(result)
                if text:
                    return text
                last_error = "Respuesta vacía del modelo"
            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)[:300]}"
                continue
        raise HTTPException(status_code=502, detail=f"Error usando Gemini. {last_error or ''}".strip())

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
    posts = repo.list_posts()
    return {str(p.get("id")): p for p in posts if isinstance(p, dict) and p.get("id")}


def _topics_store() -> Dict[str, Any]:
    topics = repo.list_topics_unused(limit=5000)
    return {str(t.get("id")): t for t in topics if isinstance(t, dict) and t.get("id")}


def _analytics_store() -> Dict[str, Any]:
    return {"pageviews": repo.get_pageviews_total(), "referrers": {}}


def track_pageview(path: str, referrer: Optional[str]) -> None:
    repo.increment_pageview(path)
    if referrer:
        repo.increment_referrer(referrer)


def list_published_posts() -> List[Dict[str, Any]]:
    items = repo.list_posts(status="published")
    items.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return items


def find_post_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    item = repo.get_post_by_slug(slug)
    if isinstance(item, dict) and item.get("status") == "published":
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
    pageviews = analytics.get("pageviews") if isinstance(analytics, dict) else {}
    pageviews = pageviews if isinstance(pageviews, dict) else {}
    total_views = sum(int(v) for v in pageviews.values() if isinstance(v, (int, float, str)) and str(v).isdigit())
    return {
        "posts": len(posts),
        "topics": len(topics),
        "pageviews_paths": len(pageviews),
        "pageviews_total": total_views,
        "ai_configured": {
            "gemini": has_real_secret(settings.GEMINI_API_KEY),
            "groq": has_real_secret(settings.GROQ_API_KEY),
            "openai": has_real_secret(settings.OPENAI_API_KEY),
        },
        "status": "ok",
    }

@router.get("/organic/models")
async def gemini_models():
    _, _, client_gemini = _get_ai_clients()
    if not client_gemini:
        return {"gemini_configured": False, "models": []}
    available = _list_gemini_models(client_gemini)
    return {
        "gemini_configured": True,
        "preferred": _pick_gemini_models(client_gemini),
        "models": available,
    }


@router.post("/organic/ingest-feeds")
async def ingest_feeds(payload: FeedIngestRequest):
    topics_existing = {}
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
                    if topic_id in topics_existing:
                        continue
                    topic = {
                        "id": topic_id,
                        "title": title,
                        "link": link,
                        "source": url,
                        "created_at": utc_now_iso(),
                        "used": False,
                    }
                    repo.upsert_topic(topic)
                    created += 1
            except Exception:
                continue
    return {"created": created}


def _pick_topic(max_candidates: int, niche: str) -> Optional[Dict[str, Any]]:
    candidates = repo.list_topics_unused(limit=max_candidates)
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
- Incluye: 1 H1, 6-10 H2, listas, ejemplos y pasos accionables.
- Optimiza para intención de búsqueda (informativa + comercial suave).
- Integra naturalmente 8-15 palabras clave secundarias y sinónimos relacionados al tema.
- Añade una sección "Preguntas frecuentes" con 5 FAQs (pregunta en <h3> + respuesta en <p>).
- Añade al final un bloque JSON-LD FAQPage dentro de <script type="application/ld+json"> (válido) con esas 5 FAQs.
- Añade enlaces internos:
  - Un enlace a /blog con el anchor "ver más artículos".
  - Un enlace al home / con el anchor "TrafficForge AI".
- Añade un CTA suave al final:
  - Debe invitar a probar {brand} para automatizar marketing (sin promesas exageradas).
  - Debe incluir un enlace HTML clickable a: {landing}
- Buenas prácticas: párrafos cortos, tablas solo si aporta, y evita relleno.
- Devuelve SOLO HTML válido (sin markdown, sin ```), empezando por <h1> y sin <html>/<head>/<body>.

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
    repo.upsert_post(post)
    topic_id = str(topic.get("id") or "")
    if topic_id:
        repo.mark_topic_used(topic_id, post_id=post_id, used_at=utc_now_iso())

    return {"post_id": post_id, "slug": slug, "status": "draft"}


@router.post("/organic/publish-post")
async def publish_post(payload: PublishRequest):
    post = None
    posts = repo.list_posts()
    for p in posts:
        if isinstance(p, dict) and p.get("id") == payload.post_id:
            post = p
            break
    if not isinstance(post, dict):
        raise HTTPException(status_code=404, detail="Post no encontrado.")

    post["status"] = "published"
    post["published_at"] = utc_now_iso()
    repo.upsert_post(post)

    return {"status": "published", "url": f"/blog/{post.get('slug')}"}


async def run_daily_pipeline() -> None:
    await _run_daily_pipeline_with_fallback(provider_preference="gemini")


async def _run_daily_pipeline_with_fallback(provider_preference: Provider) -> None:
    topics = _topics_store()
    if len(topics) < 10:
        try:
            await ingest_feeds(FeedIngestRequest())
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

    providers: List[Provider] = [provider_preference]
    for p in ["gemini", "groq", "openai"]:
        if p not in providers:
            providers.append(p)  # type: ignore[arg-type]

    last_error: Optional[str] = None
    for provider in providers:
        try:
            if provider == "gemini" and not has_real_secret(settings.GEMINI_API_KEY):
                continue
            if provider == "groq" and not has_real_secret(settings.GROQ_API_KEY):
                continue
            if provider == "openai" and not has_real_secret(settings.OPENAI_API_KEY):
                continue

            generated = await generate_post(GeneratePostRequest(provider=provider))
            post_id = generated.get("post_id")
            if post_id:
                await publish_post(PublishRequest(post_id=post_id))
            return
        except HTTPException as e:
            last_error = str(e.detail)
            continue
        except Exception as e:
            last_error = f"{type(e).__name__}: {str(e)[:300]}"
            continue

    raise HTTPException(status_code=502, detail=f"No se pudo generar el post con ningún proveedor. {last_error or ''}".strip())


@router.post("/organic/run-now")
async def run_now(provider: Provider = "gemini"):
    try:
        await _run_daily_pipeline_with_fallback(provider_preference=provider)
        return {"status": "ok", "provider_used_preference": provider}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)[:500]}")


@router.get("/blog", response_class=HTMLResponse, include_in_schema=False)
async def blog_index(request: Request):
    posts = list_published_posts()
    track_pageview("/blog", request.headers.get("referer"))
    template = templates.env.get_template("blog_index.html")
    base = _effective_public_base_url(request)
    html = template.render(
        request=request,
        posts=posts,
        google_site_verification=settings.GOOGLE_SITE_VERIFICATION,
        canonical_url=f"{base}/blog",
        og_url=f"{base}/blog",
        meta_description="Contenido educativo para atraer tráfico orgánico y convertir sin spam.",
    )
    return HTMLResponse(content=html)


@router.get("/blog/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def blog_post(slug: str, request: Request):
    post = find_post_by_slug(slug)
    if not post:
        raise HTTPException(status_code=404, detail="Artículo no encontrado.")
    track_pageview(f"/blog/{slug}", request.headers.get("referer"))
    template = templates.env.get_template("blog_post.html")
    base = _effective_public_base_url(request)
    canonical = f"{base}/blog/{slug}"
    html = template.render(
        request=request,
        post=post,
        google_site_verification=settings.GOOGLE_SITE_VERIFICATION,
        canonical_url=canonical,
        og_url=canonical,
        meta_description=_meta_description_from_html(str(post.get("content_html") or "")),
    )
    return HTMLResponse(content=html)


@router.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots(request: Request):
    base = _effective_public_base_url(request)
    return f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap(request: Request):
    posts = list_published_posts()
    base = _effective_public_base_url(request)
    urls = [f"<url><loc>{base}/</loc></url>", f"<url><loc>{base}/blog</loc></url>"]
    for p in posts[:2000]:
        slug = p.get("slug")
        if slug:
            urls.append(f"<url><loc>{base}/blog/{slug}</loc></url>")
    body = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
    body += "\n".join(urls)
    body += "\n</urlset>\n"
    return Response(content=body, media_type="application/xml")


@router.get("/sitemaps.xml", include_in_schema=False)
async def sitemap_alias(request: Request):
    return await sitemap(request)
