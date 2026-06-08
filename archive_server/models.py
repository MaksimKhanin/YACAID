"""ORM models: Media (synced files + metadata) and User (UI login)."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, UniqueConstraint

from archive_server.db import Base


class Media(Base):
    __tablename__ = "media"
    __table_args__ = (UniqueConstraint("camera", "filename", name="uq_media_camera_filename"),)

    id = Column(Integer, primary_key=True)
    camera = Column(String(64), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    kind = Column(String(16), nullable=False)  # "photo" | "video"
    path = Column(String(512), nullable=False)
    thumb_path = Column(String(512), nullable=True)

    captured_at = Column(DateTime, nullable=False, index=True)
    synced_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    is_alert = Column(Boolean, nullable=False, default=False, index=True)
    detected_class = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=True)
    area = Column(Integer, nullable=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
