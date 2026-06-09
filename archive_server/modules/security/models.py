"""ORM models for the security module: archived camera media and AI-detection metadata.

Media is shared across the whole household (everyone in the family sees the same
cameras/alerts) — unlike per-user module data such as finance or diet logs, it carries
no user_id/owner column.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, UniqueConstraint

from archive_server.core.db import Base


class AlarmState(Base):
    """Single-row table tracking the household alarm arm/disarm state."""
    __tablename__ = "alarm_state"
    id = Column(Integer, primary_key=True, default=1)
    active = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
