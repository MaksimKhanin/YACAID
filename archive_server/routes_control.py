"""Proxies camera control actions (alarm on/off, ad-hoc photo/record) to the recorder's
local control API, reachable only over a private tunnel (Tailscale/WireGuard)."""
import requests
from fastapi import APIRouter, Depends, HTTPException

from archive_server.auth import get_current_user
from archive_server.config import settings
from logger_setup import get_logger

router = APIRouter(prefix="/control", dependencies=[Depends(get_current_user)])
logger = get_logger("routes_control")


def _proxy(camera: str, action: str):
    if not settings.control_base_url:
        raise HTTPException(status_code=503, detail="Control API не сконфигурирован")

    try:
        response = requests.post(
            f"{settings.control_base_url.rstrip('/')}/control/{camera}/{action}",
            headers={"Authorization": f"Bearer {settings.control_token}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Не удалось выполнить команду управления {camera}/{action}: {e}")
        raise HTTPException(status_code=502, detail="Recorder control API недоступен")


@router.post("/{camera}/{action}")
def camera_control(camera: str, action: str):
    return _proxy(camera, action)
