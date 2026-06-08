"""Parses the recorder's filename conventions to recover capture timestamps and media kind."""
import re
from datetime import datetime
from typing import Optional

# 2026-02-08_11-18-06_camera_1_video_done.mp4
_VIDEO_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_")
# 26-02-08T-13-11-59_captured_3800_0.4713_person_done_post.jpg
_ALERT_TS_RE = re.compile(r"^(\d{2}-\d{2}-\d{2}T-\d{2}-\d{2}-\d{2})_captured")

_VIDEO_TS_FMT = "%Y-%m-%d_%H-%M-%S"
_ALERT_TS_FMT = "%y-%m-%dT-%H-%M-%S"


def guess_kind(filename: str) -> str:
    return "video" if filename.lower().endswith((".mp4", ".mov", ".avi")) else "photo"


def parse_captured_at(filename: str) -> Optional[datetime]:
    match = _ALERT_TS_RE.match(filename)
    if match:
        try:
            return datetime.strptime(match.group(1), _ALERT_TS_FMT)
        except ValueError:
            pass

    match = _VIDEO_TS_RE.match(filename)
    if match:
        try:
            return datetime.strptime(match.group(1), _VIDEO_TS_FMT)
        except ValueError:
            pass

    return None
