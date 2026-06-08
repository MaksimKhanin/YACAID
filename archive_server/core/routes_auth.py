"""Login/logout — common to every module, since the user account is shared platform-wide."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from archive_server.core.auth import (
    authenticate, clear_session_cookie, get_optional_user, set_session_cookie,
)
from archive_server.core.db import get_db
from archive_server.core.templating import templates
from logger_setup import get_logger

router = APIRouter()
logger = get_logger("auth")


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, user=Depends(get_optional_user)):
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate(db, username, password)
    if user is None:
        logger.warning(f"Неудачная попытка входа: username={username!r}, ip={request.client.host if request.client else '?'}")
        return templates.TemplateResponse(request, "login.html", {"error": "Неверный логин или пароль"}, status_code=401)

    logger.info(f"Вход выполнен: username={user.username} (id={user.id})")
    response = RedirectResponse("/", status_code=302)
    set_session_cookie(response, user)
    return response


@router.post("/logout")
def logout(user=Depends(get_optional_user)):
    if user:
        logger.info(f"Выход из системы: username={user.username} (id={user.id})")
    response = RedirectResponse("/login", status_code=302)
    clear_session_cookie(response)
    return response
