"""Local control surface for the recorder, replacing the old Telegram-bot command handlers.

Exposes a small token-authenticated HTTP API (meant to be reached only via a private tunnel,
e.g. Tailscale/WireGuard, from the archive server's UI) to toggle alarm mode and request
ad-hoc photos/recordings — by setting/clearing the same sentinel files the camera processes
already watch for.
"""
import os

from fastapi import FastAPI, Header, HTTPException

from logger_setup import get_logger
from recorder import signals
from recorder.config import ControlConfig

RESOURCES_DIR = "Resources"

ACTIONS = {
    "alarm-on": (signals.SIGNAL_ALARM, "set"),
    "alarm-off": (signals.SIGNAL_ALARM, "clear"),
    "photo": (signals.SIGNAL_PHOTO, "set"),
    "record": (signals.SIGNAL_RECORD, "set"),
}

logger = get_logger("control")


def create_app(camera_names, control_cfg: ControlConfig) -> FastAPI:
    app = FastAPI(title="YACAID recorder control")

    def _check_token(authorization: str = Header(default="")):
        expected = f"Bearer {control_cfg.token}"
        if not control_cfg.token or authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid or missing token")

    @app.get("/health")
    def health():
        return {"status": "ok", "cameras": list(camera_names)}

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

    return app


def run_control_server(camera_names, control_cfg: ControlConfig):
    import uvicorn
    app = create_app(camera_names, control_cfg)
    uvicorn.run(app, host=control_cfg.host, port=control_cfg.port, log_level="warning")
