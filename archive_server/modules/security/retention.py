"""Periodic storage retention: removes media (and DB rows) older than max_age_days.

Run as a standalone process/cron, e.g.:
  python -m archive_server.modules.security.retention --max-age-days 90
"""
import argparse
from datetime import datetime, timedelta
from pathlib import Path

from archive_server.core.db import SessionLocal
from archive_server.modules.security.models import Media
from logger_setup import get_logger

logger = get_logger("retention")


def run_once(max_age_days: int):
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    db = SessionLocal()
    deleted = 0
    try:
        old_media = db.query(Media).filter(Media.captured_at < cutoff).all()
        for media in old_media:
            for path_str in (media.path, media.thumb_path):
                if path_str:
                    path = Path(path_str)
                    if path.exists():
                        path.unlink(missing_ok=True)
            db.delete(media)
            deleted += 1
        db.commit()
    finally:
        db.close()

    logger.info(f"Очистка архива: удалено {deleted} записей старше {max_age_days} дней")
    return deleted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age-days", type=int, default=90)
    args = parser.parse_args()
    run_once(args.max_age_days)


if __name__ == "__main__":
    main()
