# logger_setup.py
import logging
import logging.handlers
import os
from datetime import datetime, timedelta

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def cleanup_old_logs(days=3):
    """Удаляет лог-файлы старше указанного количества дней."""
    now = datetime.now()
    for filename in os.listdir(LOG_DIR):
        filepath = os.path.join(LOG_DIR, filename)
        if os.path.isfile(filepath):
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            if now - file_time > timedelta(days=days):
                try:
                    os.remove(filepath)
                    print(f"Удалён старый лог: {filepath}")
                except Exception as e:
                    print(f"Ошибка при удалении {filepath}: {e}")

def get_logger(name, level=logging.INFO):
    """
    Создаёт и настраивает логгер с ротацией по дням и удалением старых файлов.
    :param name: имя логгера (рекомендуется: 'main', 'camera_<name>', и т.п.)
    :param level: уровень логирования
    :return: logging.Logger
    """
    cleanup_old_logs(days=3)  # чистим старые логи при создании любого логгера

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # уже настроен

    logger.setLevel(level)

    log_file = os.path.join(LOG_DIR, f"{name}.log")
    handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=3,  # хранить до 3 файлов (сегодня + 2 предыдущих дня)
        encoding="utf-8"
    )
    handler.suffix = "%Y-%m-%d"  # формат имени ротированного файла: camera1.log.2025-01-10
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Также можно добавить вывод в консоль (опционально)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    logger.setLevel(logging.INFO)

    return logger