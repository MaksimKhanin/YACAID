"""FastAPI application entrypoint for the archive server (run with `uvicorn archive_server.main:app`).

The app shell (auth, DB, templates, bottom nav) lives in `core`; each household feature
— security, and later finance/health/... — is a self-contained package under `modules`
that contributes its own routers and nav items. To add a module, build it under
`archive_server/modules/<name>/` exposing `routers` and `nav_items`, then list it below.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from archive_server.core import routes_auth
from archive_server.core.config import settings
from archive_server.core.db import Base, engine
from archive_server.core.templating import templates
from archive_server.modules import security
from logger_setup import get_logger

logger = get_logger("archive_server")

MODULES = [security]

app = FastAPI(title="YACAID Дом")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(routes_auth.router)
for module in MODULES:
    for router in module.routers:
        app.include_router(router)

nav_items = [item for module in MODULES for item in module.nav_items]
templates.env.globals["nav_items"] = nav_items
default_url = nav_items[0].url if nav_items else "/login"


@app.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse(default_url, status_code=302)


@app.on_event("startup")
def on_startup():
    Path(settings.media_root).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    logger.info("Архив-сервер запущен")
