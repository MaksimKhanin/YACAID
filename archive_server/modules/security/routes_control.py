"""Proxies camera control actions (alarm on/off, ad-hoc photo/record) to the recorder's
local control API, reachable only over a private tunnel (Tailscale/WireGuard)."""
import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from archive_server.core.auth import get_current_user
from archive_server.core.config import settings
from archive_server.core.db import get_db
from archive_server.core.templating import templates
from archive_server.modules.security.models import AlarmState
from logger_setup import get_logger

router = APIRouter(prefix="/control", dependencies=[Depends(get_current_user)])
logger = get_logger("routes_control")


def _proxy(camera: str, action: str):
    if not settings.control_base_url:
        raise HTTPException(status_code=503, detail="Control API не сконфигурирован")
    try:
        r = requests.post(
            f"{settings.control_base_url.rstrip('/')}/control/{camera}/{action}",
            headers={"Authorization": f"Bearer {settings.control_token}"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        logger.error(f"Ошибка команды управления {camera}/{action}: {e}")
        raise HTTPException(status_code=502, detail="Recorder control API недоступен")


def _proxy_all(action: str):
    if not settings.control_base_url:
        raise HTTPException(status_code=503, detail="Control API не сконфигурирован")
    try:
        r = requests.post(
            f"{settings.control_base_url.rstrip('/')}/control/all/{action}",
            headers={"Authorization": f"Bearer {settings.control_token}"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        logger.error(f"Ошибка команды управления для всех камер {action}: {e}")
        raise HTTPException(status_code=502, detail="Recorder control API недоступен")


def _alarm_state(db: Session) -> AlarmState:
    state = db.get(AlarmState, 1)
    if state is None:
        state = AlarmState(id=1, active=False)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


@router.post("/alarm/{state}", response_class=HTMLResponse)
def set_alarm(state: str, db: Session = Depends(get_db)):
    if state not in ("on", "off"):
        raise HTTPException(status_code=400, detail="state must be 'on' or 'off'")

    action = "alarm-on" if state == "on" else "alarm-off"
    error_msg = None
    try:
        _proxy_all(action)
        alarm = _alarm_state(db)
        alarm.active = (state == "on")
        db.commit()
        logger.info(f"Охрана {'включена' if state == 'on' else 'выключена'}")
    except HTTPException as e:
        logger.warning(f"Не удалось отправить команду на рекордер: {e.detail}")
        alarm = _alarm_state(db)
        error_msg = e.detail

    html = templates.get_template("security/_alarm_status.html").render(alarm_active=alarm.active)
    if error_msg:
        html += f'<p class="error" style="margin-top:10px;font-size:13px">⚠ {error_msg}</p>'
    return HTMLResponse(html)


@router.post("/{camera}/{action}")
def camera_control(camera: str, action: str):
    return _proxy(camera, action)
