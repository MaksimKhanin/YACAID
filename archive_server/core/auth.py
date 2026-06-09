"""Username/password login with signed session cookies (no external session store needed)."""
from datetime import datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from archive_server.core.config import settings
from archive_server.core.db import get_db
from archive_server.core.models import User

SESSION_COOKIE_NAME = "yacaid_session"
SESSION_MAX_AGE_SEC = 60 * 60 * 24 * 30  # 30 days

_serializer = URLSafeTimedSerializer(settings.session_secret, salt="yacaid-session")


class NotAuthenticatedException(Exception):
    """No valid session — the app-level exception handler redirects to /login."""
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def authenticate(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def create_session_cookie(user: User) -> str:
    return _serializer.dumps({"uid": user.id, "username": user.username})


def _read_session(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        return _serializer.loads(token, max_age=SESSION_MAX_AGE_SEC)
    except BadSignature:
        return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    data = _read_session(request)
    if not data:
        raise NotAuthenticatedException()
    user = db.get(User, data["uid"])
    if user is None:
        raise NotAuthenticatedException()
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)):
    data = _read_session(request)
    if not data:
        return None
    return db.get(User, data["uid"])


def set_session_cookie(response, user: User):
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_cookie(user),
        max_age=SESSION_MAX_AGE_SEC,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_session_cookie(response):
    response.delete_cookie(SESSION_COOKIE_NAME)
