"""Local control surface for the recorder — the "brains" of the household assistant.

Exposes a small token-authenticated HTTP API (meant to be reached only via a private tunnel,
e.g. Tailscale/WireGuard, from the archive server's UI) to:
  - toggle camera alarm mode and request ad-hoc photos/recordings, by setting/clearing the
    same sentinel files the camera processes already watch for;
  - orchestrate the rest of the smart home by proxying to a Home Assistant instance, so the
    recorder doesn't need to reimplement device drivers — it just calls HA's REST API.
"""
import os

import requests
from fastapi import Body, FastAPI, Header, HTTPException

from logger_setup import get_logger
from recorder import signals
from recorder.config import ControlConfig, HomeAssistantConfig
from recorder.home_assistant import HomeAssistantClient

RESOURCES_DIR = "Resources"

ACTIONS = {
    "alarm-on": (signals.SIGNAL_ALARM, "set"),
    "alarm-off": (signals.SIGNAL_ALARM, "clear"),
    "photo": (signals.SIGNAL_PHOTO, "set"),
    "record": (signals.SIGNAL_RECORD, "set"),
}

logger = get_logger("control")


def create_app(camera_names, control_cfg: ControlConfig, ha_cfg: HomeAssistantConfig = None) -> FastAPI:
    app = FastAPI(title="YACAID recorder control")
    ha_client = HomeAssistantClient(ha_cfg.base_url, ha_cfg.token) if ha_cfg and ha_cfg.enabled else None

    def _check_token(authorization: str = Header(default="")):
        expected = f"Bearer {control_cfg.token}"
        if not control_cfg.token or authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid or missing token")

    def _require_ha() -> HomeAssistantClient:
        if ha_client is None:
            raise HTTPException(status_code=503, detail="Home Assistant не сконфигурирован")
        return ha_client

    @app.get("/health")
    def health():
        return {"status": "ok", "cameras": list(camera_names), "home_assistant": ha_client is not None}

    @app.post("/control/{camera}/{action}")
    def control(camera: str, action: str, authorization: str = Header(default="")):
        _check_token(authorization)

        if camera not in camera_names:
            raise HTTPException(status_code=404, detail=f"Unknown camera '{camera}'")
        if action not in ACTIONS:
            raise HTTPException(status_code=400, detail=f"Unknown action '{action}'")

        signal_name, op = ACTIONS[action]
        camera_dir = os.path.join(RESOURCES_DIR, camera)

        if op == "set":
            signals.set_signal(camera_dir, signal_name)
        else:
            signals.clear_signal(camera_dir, signal_name)

        logger.info(f"Получена команда управления: камера={camera}, действие={action}")
        return {"camera": camera, "action": action, "status": "ok"}

    @app.post("/control/all/{action}")
    def control_all(action: str, authorization: str = Header(default="")):
        _check_token(authorization)

        if action not in ACTIONS:
            raise HTTPException(status_code=400, detail=f"Unknown action '{action}'")

        signal_name, op = ACTIONS[action]
        for camera in camera_names:
            camera_dir = os.path.join(RESOURCES_DIR, camera)
            if op == "set":
                signals.set_signal(camera_dir, signal_name)
            else:
                signals.clear_signal(camera_dir, signal_name)

        logger.info(f"Получена команда управления для всех камер: действие={action}")
        return {"action": action, "cameras": list(camera_names), "status": "ok"}

    @app.post("/ha/service/{domain}/{service}")
    def ha_call_service(domain: str, service: str, payload: dict = Body(default={}),
                        authorization: str = Header(default="")):
        _check_token(authorization)
        client = _require_ha()
        try:
            result = client.call_service(domain, service, **payload)
        except requests.RequestException as e:
            logger.error(f"Ошибка вызова HA-сервиса {domain}.{service}: {e}")
            raise HTTPException(status_code=502, detail="Home Assistant недоступен")
        return {"domain": domain, "service": service, "result": result}

    @app.get("/ha/state/{entity_id}")
    def ha_state(entity_id: str, authorization: str = Header(default="")):
        _check_token(authorization)
        client = _require_ha()
        try:
            return client.get_state(entity_id)
        except requests.RequestException as e:
            logger.error(f"Ошибка получения состояния {entity_id}: {e}")
            raise HTTPException(status_code=502, detail="Home Assistant недоступен")

    @app.get("/ha/states")
    def ha_states(authorization: str = Header(default="")):
        _check_token(authorization)
        client = _require_ha()
        try:
            return client.get_states()
        except requests.RequestException as e:
            logger.error(f"Ошибка получения списка состояний HA: {e}")
            raise HTTPException(status_code=502, detail="Home Assistant недоступен")

    return app


def run_control_server(camera_names, control_cfg: ControlConfig, ha_cfg: HomeAssistantConfig = None):
    import uvicorn
    app = create_app(camera_names, control_cfg, ha_cfg)
    uvicorn.run(app, host=control_cfg.host, port=control_cfg.port, log_level="warning")
