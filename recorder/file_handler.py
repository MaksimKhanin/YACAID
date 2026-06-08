"""Watches Resources/ for finished media, merges video chunks, syncs alerts to the archive
server, and prunes old local files.

Filename conventions produced by camera_stream/recorder:
  *_done.*                regular finished chunk/snapshot, kept locally and merged/cleaned up
  *_done_post.*           finished chunk/snapshot that should be pushed to the archive server
  *_done_post_alarm.*     same, additionally flagged as an AI-confirmed alert
"""
import os
import subprocess
import threading
import time
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional, Set

from logger_setup import get_logger
from recorder import signals
from recorder.archive_sync import ArchiveSyncClient

POST_MARKER = "_done_post"
ALARM_MARKER = "_alarm"
MERGE_LIST_FILENAME = "videos_to_merge.txt"


class FileHandler:
    def __init__(
            self,
            watch_dir: str,
            file_pattern: str = "*",
            extensions: Optional[Set[str]] = None,
            scan_interval: float = 5.0,
            merge_interval_sec: float = 60 * 60,
            cleanup_interval_sec: float = 60 * 60,
            max_local_age_hours: int = 12,
            archive_sync: Optional[ArchiveSyncClient] = None,
    ):
        self.watch_dir = Path(watch_dir).resolve()
        self.file_pattern = file_pattern
        self.extensions = {ext.lower() for ext in extensions} if extensions else None
        self.scan_interval = scan_interval
        self.merge_interval_sec = merge_interval_sec
        self.cleanup_interval_sec = cleanup_interval_sec
        self.max_local_age_hours = max_local_age_hours
        self.archive_sync = archive_sync

        self.logger = get_logger("FileHandler")
        self._running = False
        self._thread = None

        if not self.watch_dir.exists():
            raise ValueError(f"Директория не существует: {self.watch_dir}")

        self.logger.info(
            f"Инициализирован FileHandler: директория={self.watch_dir}, "
            f"шаблон='{file_pattern}', расширения={extensions or 'все'}, "
            f"архив-синхронизация={'включена' if archive_sync and archive_sync.enabled else 'выключена'}"
        )

    # -- retention ---------------------------------------------------------

    def _cleanup_old_files(self):
        cutoff_time = time.time() - (self.max_local_age_hours * 3600)
        deleted = 0
        try:
            for file_path in self.watch_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                if file_path.name in (MERGE_LIST_FILENAME,) or file_path.name in signals.ALL_SIGNALS:
                    continue
                if file_path.stat().st_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        deleted += 1
                    except Exception as e:
                        self.logger.warning(f"Не удалось удалить {file_path}: {e}")
            if deleted:
                self.logger.info(f"Очистка: удалено {deleted} файлов старше {self.max_local_age_hours} часов")
        except Exception:
            self.logger.exception("Ошибка при очистке старых файлов")

    # -- video merging ------------------------------------------------------

    def _merge_videos_in_folder(self, folder_path: Path) -> Optional[Path]:
        video_files = sorted(f for f in folder_path.glob("*.mp4") if "_done" in f.name)
        if len(video_files) < 2:
            return None

        list_file = folder_path / MERGE_LIST_FILENAME
        with open(list_file, "w") as f:
            for vf in video_files:
                f.write(f"file '{vf.resolve().as_posix()}'\n")

        output_file = folder_path / f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output_file)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                self.logger.error(f"Ошибка ffmpeg при объединении видео: {result.stderr}")
                return None

            self.logger.info(f"Видео объединены: {output_file}")
            for vf in video_files:
                vf.unlink()
            list_file.unlink()
            return output_file
        except subprocess.TimeoutExpired:
            self.logger.error("Таймаут при объединении видео")
            return None
        except Exception:
            self.logger.exception("Исключение при объединении видео")
            return None

    def _merge_all_cameras(self):
        self.logger.info("Запуск объединения видео по камерам")
        for camera_folder in self.watch_dir.iterdir():
            if camera_folder.is_dir():
                self._merge_videos_in_folder(camera_folder)

    # -- scanning / sync ----------------------------------------------------

    def _matches_criteria(self, file_path: Path) -> bool:
        if self.extensions is not None and file_path.suffix.lower().lstrip('.') not in self.extensions:
            return False
        return fnmatch(file_path.name, self.file_pattern)

    def _process_file(self, file_path: Path):
        if POST_MARKER not in file_path.name:
            return

        if self.archive_sync is None or not self.archive_sync.enabled:
            return

        camera_name = file_path.parent.name
        is_alert = ALARM_MARKER in file_path.name

        synced_or_dropped = self.archive_sync.sync_file(file_path, camera_name=camera_name, is_alert=is_alert)
        if not synced_or_dropped:
            return

        new_name = file_path.name.replace("_post", "")
        new_path = file_path.parent / new_name
        try:
            os.rename(file_path, new_path)
        except FileNotFoundError:
            pass

    def _scan_and_process(self):
        try:
            for file_path in self.watch_dir.rglob("*"):
                if file_path.is_file() and self._matches_criteria(file_path):
                    self._process_file(file_path)
        except Exception:
            self.logger.exception("Ошибка при сканировании директории")

    # -- lifecycle -----------------------------------------------------------

    def start(self):
        if self._running:
            self.logger.warning("FileHandler уже запущен")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="file-handler")
        self._thread.start()
        self.logger.info("FileHandler запущен")

    def _run(self):
        last_merge_time = 0.0
        last_cleanup_time = 0.0

        while self._running:
            now = time.time()
            self._scan_and_process()

            if now - last_merge_time >= self.merge_interval_sec:
                self._merge_all_cameras()
                last_merge_time = now

            if now - last_cleanup_time >= self.cleanup_interval_sec:
                self._cleanup_old_files()
                last_cleanup_time = now

            time.sleep(self.scan_interval)

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.logger.info("FileHandler остановлен")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
