from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from datetime import datetime, timezone
from .core.config import settings
from .core.scheduler import start_scheduler, stop_scheduler
from .core import repo
from .modules import traffic, automation, chatbot, funnel, email_service, analysis, organic

app = FastAPI(title=settings.PROJECT_NAME, docs_url=None, redoc_url=None)

# Configuración de Jinja2
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@app.get("/docs", include_in_schema=False)
async def docs():
    response = get_swagger_ui_html(openapi_url="/openapi.json", title=f"{settings.PROJECT_NAME} - API")
    html = response.body.decode("utf-8", errors="ignore")
    banner = (
        "<div style=\"padding:12px 16px;background:#0f172a;color:#fff;"
        "font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial;"
        "display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:9999;\">"
        "<a href=\"/\" style=\"color:#fff;text-decoration:none;font-weight:800;\">← Volver al Dashboard</a>"
        "<a href=\"/blog\" style=\"color:#cbd5e1;text-decoration:none;font-weight:700;\">Blog</a>"
        "<a href=\"/bots\" style=\"color:#cbd5e1;text-decoration:none;font-weight:700;\">Bots</a>"
        "<a href=\"/leads\" style=\"color:#cbd5e1;text-decoration:none;font-weight:700;\">Leads</a>"
        "</div>"
    )
    if "<body>" in html:
        html = html.replace("<body>", f"<body>{banner}", 1)
    return HTMLResponse(content=html)


def _compute_stats():
    pageviews_today = repo.get_pageviews_today()
    visitors = int(sum(int(v) for v in pageviews_today.values()))

    leads_captured = len(repo.list_leads())

    published_posts = sum(1 for p in repo.list_posts(status="published") if isinstance(p, dict))

    conversion_rate = "0%"
    if visitors > 0:
        conversion_rate = f"{(leads_captured / visitors) * 100:.1f}%"

    return {
        "visitors": visitors,
        "leads_captured": leads_captured,
        "conversion_rate": conversion_rate,
        "published_posts": published_posts,
    }


def _format_today_es() -> str:
    now = datetime.now(timezone.utc)
    months = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    return f"{now.day:02d} de {months[now.month - 1]}, {now.year}"

def _bots_preview():
    return repo.list_tasks(limit=8)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    Renderiza el Dashboard principal de TrafficForge AI.
    """
    stats = _compute_stats()
    template = templates.env.get_template("dashboard.html")
    html = template.render(
        request=request,
        stats=stats,
        bots=_bots_preview(),
        landing_url=settings.LANDING_PAGE_URL,
        today_label=_format_today_es(),
    )
    return HTMLResponse(content=html)


@app.get("/api/dashboard", include_in_schema=False)
async def dashboard_api():
    stats = _compute_stats()
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    bots = _bots_preview()
    return JSONResponse({"stats": stats, "bots": bots, "now": now, "today": _format_today_es()})

@app.get("/bots", response_class=HTMLResponse, include_in_schema=False)
async def bots_page(request: Request):
    bots = repo.list_tasks(limit=200)
    template = templates.env.get_template("bots.html")
    html = template.render(request=request, bots=bots, landing_url=settings.LANDING_PAGE_URL)
    return HTMLResponse(content=html)

@app.get("/leads", response_class=HTMLResponse, include_in_schema=False)
async def leads_page(request: Request):
    leads_list = repo.list_leads()
    sources = {}
    conversions_whatsapp = 0
    for lead in leads_list:
        if not isinstance(lead, dict):
            continue
        source = str(lead.get("source") or "unknown")
        sources[source] = int(sources.get(source, 0)) + 1
        if str(lead.get("whatsapp") or "").strip():
            conversions_whatsapp += 1

    stats = {
        "total_leads": len(leads_list),
        "conversions_whatsapp": conversions_whatsapp,
        "sales_closed": 0,
        "sources": sources,
    }
    template = templates.env.get_template("leads.html")
    html = template.render(request=request, stats=stats, landing_url=settings.LANDING_PAGE_URL)
    return HTMLResponse(content=html)

@app.get("/subscription", response_class=HTMLResponse, include_in_schema=False)
async def subscription_page(request: Request):
    template = templates.env.get_template("subscription.html")
    html = template.render(request=request, landing_url=settings.LANDING_PAGE_URL)
    return HTMLResponse(content=html)

@app.middleware("http")
async def analytics_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/blog"):
        organic.track_pageview(path, request.headers.get("referer"))
    return response

@app.on_event("startup")
async def on_startup():
    start_scheduler(organic.run_daily_pipeline)


@app.on_event("shutdown")
async def on_shutdown():
    stop_scheduler()

# Incluir routers
app.include_router(traffic.router, prefix="/traffic", tags=["Traffic"])
app.include_router(automation.router, prefix="/automation", tags=["Automation"])
app.include_router(chatbot.router, prefix="/chatbot", tags=["Chatbot"])
app.include_router(funnel.router, prefix="/funnel", tags=["Funnel"])
app.include_router(email_service.router, prefix="/email", tags=["Email"])
app.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
app.include_router(organic.router, tags=["Organic"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
