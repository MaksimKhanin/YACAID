"""Ingest endpoint: receives uploaded media from the recorder's archive_sync client."""
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from archive_server.config import settings
from archive_server.db import get_db
from archive_server.filenames import guess_kind, parse_captured_at
from archive_server.models import Media
from archive_server.thumbnails import generate_thumbnail
from logger_setup import get_logger

router = APIRouter()
logger = get_logger("ingest")


def _check_api_key(authorization: str = Header(default="")):
    expected = f"Bearer {settings.ingest_api_key}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/api/media")
async def ingest_media(
    file: UploadFile = File(...),
    camera: str = Form(...),
    filename: str = Form(...),
    is_alert: bool = Form(False),
    detected_class: str = Form(None),
    confidence: float = Form(None),
    area: int = Form(None),
    db: Session = Depends(get_db),
    _=Depends(_check_api_key),
):
    existing = db.query(Media).filter(Media.camera == camera, Media.filename == filename).one_or_none()
    if existing is not None:
        logger.info(f"Файл уже проиндексирован, пропускаю: {camera}/{filename}")
        return {"status": "duplicate", "id": existing.id}

    captured_at = parse_captured_at(filename) or datetime.utcnow()
    kind = guess_kind(filename)

    camera_dir = Path(settings.media_root) / camera / captured_at.strftime("%Y-%m-%d")
    camera_dir.mkdir(parents=True, exist_ok=True)
    dest_path = camera_dir / filename

    with open(dest_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)

    thumb_path = generate_thumbnail(dest_path, kind)

    media = Media(
        camera=camera,
        filename=filename,
        kind=kind,
        path=str(dest_path),
        thumb_path=str(thumb_path) if thumb_path else None,
        captured_at=captured_at,
        is_alert=is_alert,
        detected_class=detected_class,
        confidence=confidence,
        area=area,
    )
    db.add(media)
    db.commit()
    db.refresh(media)

    logger.info(f"Принят новый файл {camera}/{filename} (id={media.id}, alert={is_alert})")
    return {"status": "stored", "id": media.id}
