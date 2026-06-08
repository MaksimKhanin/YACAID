"""Server-rendered, mobile-first UI for the security module: alerts feed, archive
browser, camera view, media detail and raw file/thumbnail serving."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from archive_server.core.auth import get_current_user
from archive_server.core.db import get_db
from archive_server.core.templating import templates
from archive_server.modules.security.models import Media

router = APIRouter()

PAGE_SIZE = 24


def _media_query(db: Session, *, camera=None, alerts_only=False):
    q = db.query(Media).order_by(Media.captured_at.desc())
    if camera:
        q = q.filter(Media.camera == camera)
    if alerts_only:
        q = q.filter(Media.is_alert.is_(True))
    return q


def _paginate(request: Request, q, page: int):
    items = q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE + 1).all()
    has_more = len(items) > PAGE_SIZE
    return items[:PAGE_SIZE], has_more


@router.get("/alerts", response_class=HTMLResponse)
def alerts_feed(request: Request, page: int = 1, db: Session = Depends(get_db), user=Depends(get_current_user)):
    items, has_more = _paginate(request, _media_query(db, alerts_only=True), page)
    template = "security/_media_grid.html" if request.headers.get("HX-Request") else "security/alerts.html"
    return templates.TemplateResponse(request, template, {
        "items": items, "page": page, "has_more": has_more,
        "next_url": f"/alerts?page={page + 1}", "title": "Тревоги", "active_tab": "alerts",
    })


@router.get("/archive", response_class=HTMLResponse)
def archive_browser(request: Request, camera: str = None, page: int = 1,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    cameras = [row[0] for row in db.query(Media.camera).distinct().order_by(Media.camera).all()]
    items, has_more = _paginate(request, _media_query(db, camera=camera), page)

    next_url = f"/archive?page={page + 1}" + (f"&camera={camera}" if camera else "")
    template = "security/_media_grid.html" if request.headers.get("HX-Request") else "security/archive.html"
    return templates.TemplateResponse(request, template, {
        "items": items, "page": page, "has_more": has_more, "next_url": next_url,
        "cameras": cameras, "selected_camera": camera, "title": "Архив", "active_tab": "archive",
    })


@router.get("/camera/{name}", response_class=HTMLResponse)
def camera_view(request: Request, name: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    items, has_more = _paginate(request, _media_query(db, camera=name), 1)
    return templates.TemplateResponse(request, "security/camera.html", {
        "items": items, "has_more": has_more, "next_url": f"/archive?camera={name}&page=2",
        "camera": name, "title": f"Камера {name}", "active_tab": "archive",
    })


@router.get("/media/{media_id}", response_class=HTMLResponse)
def media_detail(request: Request, media_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    media = db.get(Media, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return templates.TemplateResponse(request, "security/media_detail.html", {"media": media, "title": media.filename, "active_tab": ""})


# -- raw file serving --------------------------------------------------------

@router.get("/files/{media_id}")
def serve_file(media_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    media = db.get(Media, media_id)
    if media is None or not Path(media.path).exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(media.path)


@router.get("/thumbs/{media_id}")
def serve_thumb(media_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    media = db.get(Media, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    thumb = media.thumb_path
    if not thumb or not Path(thumb).exists():
        if not Path(media.path).exists():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(media.path)
    return FileResponse(thumb)
