"""FastAPI application entrypoint for the archive server (run with `uvicorn archive_server.main:app`)."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from archive_server import ingest, routes_control, routes_ui
from archive_server.config import settings
from archive_server.db import Base, engine
from logger_setup import get_logger

logger = get_logger("archive_server")

app = FastAPI(title="YACAID Archive")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(routes_ui.router)
app.include_router(routes_control.router)
app.include_router(ingest.router)


@app.on_event("startup")
def on_startup():
    Path(settings.media_root).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    logger.info("Архив-сервер запущен")
