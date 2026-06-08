"""Pushes finished alert media to the remote archive server (replaces the old Telegram/Yandex push).

Each `_post`-suffixed file is parsed for metadata (camera, timestamp, and — for AI-confirmed
alerts — detected class/confidence/area), then POSTed as multipart/form-data to the archive
server's ingest endpoint. Successfully synced files are renamed (suffix stripped) so the
file_handler's normal scan no longer picks them up; files that fail repeatedly are dropped.
"""
import os
import re
from pathlib import Path
from typing import Optional

import requests

from logger_setup import get_logger

# 26-02-08T-13-11-59_captured_3800_0.4713_person_done_post.jpg
_ALERT_RE = re.compile(
    r"captured_(?P<area>\d+)_(?P<confidence>[\d.]+)_(?P<class_name>\w+)_done"
)

INGEST_PATH = "/api/media"


def parse_alert_metadata(filename: str) -> Optional[dict]:
    """Extract detection metadata from an alert filename, or None if it isn't an AI alert file."""
    match = _ALERT_RE.search(filename)
    if not match:
        return None
    return {
        "detected_class": match.group("class_name"),
        "confidence": float(match.group("confidence")),
        "area": int(match.group("area")),
    }


class ArchiveSyncClient:
    """HTTP client that uploads finished media files to the archive server."""

    def __init__(self, base_url: str, api_key: str, max_failures: int = 4, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_failures = max_failures
        self.timeout = timeout
        self.logger = get_logger("archive_sync")
        self._failure_count = {}

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def sync_file(self, file_path: Path, camera_name: str, is_alert: bool) -> bool:
        """Upload a single file. Returns True on success (or once max_failures is exceeded -> drop)."""
        file_str = str(file_path)
        metadata = {
            "camera": camera_name,
            "filename": file_path.name,
            "is_alert": is_alert,
        }
        alert_meta = parse_alert_metadata(file_path.name)
        if alert_meta:
            metadata.update(alert_meta)

        try:
            with open(file_path, "rb") as f:
                response = requests.post(
                    f"{self.base_url}{INGEST_PATH}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (file_path.name, f)},
                    data=metadata,
                    timeout=self.timeout,
                )
            response.raise_for_status()
            self._failure_count.pop(file_str, None)
            self.logger.info(f"Файл синхронизирован с архив-сервером: {file_str}")
            return True
        except Exception as e:
            count = self._failure_count.get(file_str, 0) + 1
            self._failure_count[file_str] = count
            self.logger.error(f"Ошибка синхронизации {file_str} (попытка {count}/{self.max_failures}): {e}")
            return count >= self.max_failures

    def forget(self, file_path: Path):
        self._failure_count.pop(str(file_path), None)
