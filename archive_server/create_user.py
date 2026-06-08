"""CLI helper to create/update a UI login user.

Usage: python -m archive_server.create_user <username> <password>
"""
import sys

from archive_server.auth import hash_password
from archive_server.db import Base, SessionLocal, engine
from archive_server.models import User


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m archive_server.create_user <username> <password>")
        raise SystemExit(1)

    username, password = sys.argv[1], sys.argv[2]

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).one_or_none()
        if user is None:
            user = User(username=username, password_hash=hash_password(password))
            db.add(user)
            print(f"Создан пользователь '{username}'")
        else:
            user.password_hash = hash_password(password)
            print(f"Обновлён пароль пользователя '{username}'")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
