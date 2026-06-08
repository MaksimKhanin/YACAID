"""Typed configuration for the recorder, loaded from cfg/cfg.yml with secret overrides from env vars.

Secrets (RTSP credentials, archive-server API key, control-API token) should not be committed in
plaintext. Prefer environment variables / an untracked cfg/cfg.local.yml that is merged on top of
the example config.
"""
import os
from dataclasses import dataclass, field
from typing import Dict

import yaml

CFG_DIR = "cfg"
CFG_FILE = "cfg.yml"
CFG_LOCAL_FILE = "cfg.local.yml"


@dataclass
class CameraConfig:
    name: str
    stream_detector: str
    stream_video: str
    motion_threshold: int = 10000
    ai_min_area: int = 500


@dataclass
class ArchiveSyncConfig:
    base_url: str = ""
    api_key: str = ""
    enabled: bool = False


@dataclass
class ControlConfig:
    host: str = "127.0.0.1"
    port: int = 8090
    token: str = ""


@dataclass
class AppConfig:
    cameras: Dict[str, CameraConfig] = field(default_factory=dict)
    archive_sync: ArchiveSyncConfig = field(default_factory=ArchiveSyncConfig)
    control: ControlConfig = field(default_factory=ControlConfig)


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_raw_yaml() -> dict:
    base_path = os.path.join(CFG_DIR, CFG_FILE)
    with open(base_path, "r", encoding="utf-8") as f:
        raw = yaml.load(f, Loader=yaml.FullLoader) or {}

    local_path = os.path.join(CFG_DIR, CFG_LOCAL_FILE)
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            local = yaml.load(f, Loader=yaml.FullLoader) or {}
        raw = _deep_merge(raw, local)

    return raw


def load_config() -> AppConfig:
    """Load and validate the application config, applying env-var overrides for secrets."""
    raw = _load_raw_yaml()

    stream_cfg = raw.get("stream_cfg") or {}
    if not stream_cfg:
        raise ValueError("Конфигурация не содержит ни одной камеры (stream_cfg пуст)")

    cameras = {}
    for cam_name, cam_raw in stream_cfg.items():
        try:
            cameras[cam_name] = CameraConfig(
                name=cam_name,
                stream_detector=cam_raw["stream_detector"],
                stream_video=cam_raw.get("stream_video", cam_raw["stream_detector"]),
                motion_threshold=cam_raw.get("motion_threshold", 10000),
                ai_min_area=cam_raw.get("ai_min_area", 500),
            )
        except KeyError as e:
            raise ValueError(f"Камера '{cam_name}' не содержит обязательного поля {e}")

    archive_raw = raw.get("archive_sync") or {}
    archive_sync = ArchiveSyncConfig(
        base_url=os.environ.get("ARCHIVE_BASE_URL", archive_raw.get("base_url", "")),
        api_key=os.environ.get("ARCHIVE_API_KEY", archive_raw.get("api_key", "")),
        enabled=bool(os.environ.get("ARCHIVE_BASE_URL", archive_raw.get("base_url", ""))),
    )

    control_raw = raw.get("control") or {}
    control = ControlConfig(
        host=control_raw.get("host", "127.0.0.1"),
        port=int(control_raw.get("port", 8090)),
        token=os.environ.get("CONTROL_API_TOKEN", control_raw.get("token", "")),
    )

    return AppConfig(cameras=cameras, archive_sync=archive_sync, control=control)
