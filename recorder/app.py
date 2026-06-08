"""Process orchestration / entrypoint for the recorder.

Spawns one process per camera plus a file-handler process (archive sync, video merging,
retention cleanup) and an optional local control-API process, and supervises them —
restarting any process that dies instead of tearing the whole system down.
"""
import multiprocessing
import os
import time

from logger_setup import get_logger
from recorder.archive_sync import ArchiveSyncClient
from recorder.camera_stream import CameraStream
from recorder.config import AppConfig, load_config
from recorder.control import run_control_server
from recorder.file_handler import FileHandler

RESOURCES_DIR = "Resources"
SUPERVISOR_INTERVAL_SEC = 30

main_logger = get_logger("main")


def _camera_proc(cam_cfg):
    main_logger.info(f"Запуск процесса для камеры {cam_cfg.name}")
    try:
        stream = CameraStream(
            camera_name=cam_cfg.name,
            stream_url=cam_cfg.stream_detector,
            motion_threshold=cam_cfg.motion_threshold,
            min_area=cam_cfg.ai_min_area,
        )
        stream.run()
    except Exception:
        main_logger.exception(f"Критическая ошибка в процессе камеры {cam_cfg.name}")


def _file_handler_proc(archive_cfg):
    main_logger.info("Запуск file_handler")
    sync_client = ArchiveSyncClient(base_url=archive_cfg.base_url, api_key=archive_cfg.api_key)
    handler = FileHandler(
        watch_dir=RESOURCES_DIR,
        file_pattern="*_done*",
        extensions={"jpg", "mp4"},
        scan_interval=5.0,
        archive_sync=sync_client,
    )
    handler.start()
    while True:
        time.sleep(60)


def _control_proc(camera_names, control_cfg, ha_cfg):
    suffix = " (с интеграцией Home Assistant)" if ha_cfg.enabled else ""
    main_logger.info(f"Запуск control-API на {control_cfg.host}:{control_cfg.port}{suffix}")
    run_control_server(camera_names, control_cfg, ha_cfg)


class ProcessSpec:
    def __init__(self, name, target, args=()):
        self.name = name
        self.target = target
        self.args = args
        self.process = None

    def start(self):
        self.process = multiprocessing.Process(target=self.target, args=self.args, name=self.name)
        self.process.start()
        return self.process

    def restart(self):
        if self.process is not None and self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=5)
        return self.start()


def build_process_specs(cfg: AppConfig):
    specs = [ProcessSpec("file_handler", _file_handler_proc, args=(cfg.archive_sync,))]

    if cfg.control.token:
        specs.append(ProcessSpec("control_api", _control_proc,
                                 args=(list(cfg.cameras.keys()), cfg.control, cfg.home_assistant)))
    else:
        main_logger.warning("CONTROL_API_TOKEN не задан — локальный control-API отключён")

    for cam_cfg in cfg.cameras.values():
        specs.append(ProcessSpec(f"camera_{cam_cfg.name}", _camera_proc, args=(cam_cfg,)))

    return specs


def supervise(specs):
    try:
        while True:
            time.sleep(SUPERVISOR_INTERVAL_SEC)
            for spec in specs:
                if not spec.process.is_alive():
                    main_logger.critical(f"Процесс упал: {spec.name}. Перезапускаю...")
                    spec.restart()
    except KeyboardInterrupt:
        main_logger.info("Получен сигнал остановки")
    except Exception:
        main_logger.exception("Критическая ошибка в основном цикле")
    finally:
        main_logger.info("Завершение работы: остановка всех процессов")
        for spec in specs:
            if spec.process is not None and spec.process.is_alive():
                spec.process.terminate()
        main_logger.info("=== СИСТЕМА ОСТАНОВЛЕНА ===")


def main():
    main_logger.info("=== ЗАПУСК СИСТЕМЫ МОНИТОРИНГА ===")

    app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(app_path)
    os.makedirs(RESOURCES_DIR, exist_ok=True)

    cfg = load_config()
    specs = build_process_specs(cfg)

    for spec in specs:
        spec.start()
        main_logger.info(f"Запущен процесс: {spec.name}")

    supervise(specs)


if __name__ == "__main__":
    main()
