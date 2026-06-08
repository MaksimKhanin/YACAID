"""ORM models shared by all modules: User (UI login, common to the whole household)."""
from sqlalchemy import Column, Integer, String

from archive_server.core.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
