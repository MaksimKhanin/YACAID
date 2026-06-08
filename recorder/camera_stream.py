"""Per-camera RTSP capture loop: orchestrates motion detection, AI confirmation and recording."""
import os
import time
from datetime import datetime

import cv2

from logger_setup import get_logger
from recorder import signals
from recorder.detector import AIdetector
from recorder.motion import MotionDetector
from recorder.recorder import VideoRecorder

RESOURCES_DIR = "Resources"

RECONNECT_DELAY_SEC = 5
MAX_RECONNECT_ATTEMPTS = 10
SIGNAL_REFRESH_INTERVAL_SEC = 10
MOTION_COOLDOWN_SEC = 5

# Frames of "quiet" stream required before motion is allowed to trigger detection again,
# and consecutive AI-confirmed frames required before an alert is raised.
FRAMES_BEFORE_RETRIGGER = 30
AI_CONFIRMATION_FRAMES = 3


class CameraStream:
    """Captures an RTSP stream, detects motion/objects, records rolling chunks and snapshots."""

    def __init__(self, camera_name, stream_url, motion_threshold=10000, min_area=500):
        self.camera_name = str(camera_name)
        self.stream_url = stream_url

        self.logger = get_logger(f"camera_{self.camera_name}")

        self.camera_dir = os.path.join(RESOURCES_DIR, self.camera_name)
        os.makedirs(self.camera_dir, exist_ok=True)

        self.motion = MotionDetector(motion_threshold=motion_threshold)
        self.ai_detector = AIdetector(min_area=min_area)

        # External-signal state, refreshed periodically from sentinel files.
        self.alarm_active = False
        self.photo_requested = False
        self.record_requested = False

        # Motion -> AI confirmation bookkeeping.
        self._frames_since_last_alert = 0
        self._frames_since_motion_check = 0
        self._ai_confirmations = 0
        self._last_alert_time = 0.0

    # -- external signals -------------------------------------------------

    def _refresh_signals(self):
        self.photo_requested = self.photo_requested or signals.has_signal(self.camera_dir, signals.SIGNAL_PHOTO)
        self.record_requested = self.record_requested or signals.has_signal(self.camera_dir, signals.SIGNAL_RECORD)
        self.alarm_active = signals.has_signal(self.camera_dir, signals.SIGNAL_ALARM)

    # -- per-frame processing ---------------------------------------------

    def _build_rtsp_url(self):
        url = self.stream_url
        if "rtsp://" in url and "timeout=" not in url:
            url += "?timeout=60000000"  # 60s, in microseconds
        return url

    def _check_for_alert(self, frame, now):
        """Run AI confirmation on motion; returns True if an alert should be raised this frame."""
        if not self.alarm_active:
            return False
        if now - self._last_alert_time <= MOTION_COOLDOWN_SEC:
            return False
        if self._frames_since_motion_check <= FRAMES_BEFORE_RETRIGGER:
            return False
        if not self.motion.has_motion(frame):
            return False

        self._frames_since_motion_check = 0
        detection = self.ai_detector.process_image(frame)

        if detection is None:
            self._ai_confirmations = 0
            return False

        self._ai_confirmations += 1
        self.logger.info(
            f"{self.camera_name}: {detection.class_name} обнаружен, площадь={detection.area}, "
            f"уверенность={detection.confidence:.2f} (подтверждений: {self._ai_confirmations})"
        )

        if self._ai_confirmations <= AI_CONFIRMATION_FRAMES:
            return False

        self._ai_confirmations = 0
        self._last_alert_time = now
        self._save_alert_snapshot(detection)
        return True

    def _save_alert_snapshot(self, detection):
        prefix = datetime.now().strftime("%y-%m-%dT-%H-%M-%S")
        path = os.path.join(
            self.camera_dir,
            f"{prefix}_captured_{detection.area}_{detection.confidence:.4f}_{detection.class_name}_done_post.jpg",
        )
        cv2.imwrite(path, detection.image)
        self.logger.info(f"{self.camera_name}: сохранён кадр подтверждённого обнаружения -> {path}")

    def _save_requested_photo(self, frame):
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(
            self.camera_dir,
            f"{now}_{self.camera_name}_image_by_external_signal_done_post.jpg",
        )
        cv2.imwrite(path, frame)
        signals.clear_signal(self.camera_dir, signals.SIGNAL_PHOTO)
        self.photo_requested = False
        self.logger.info(f"{self.camera_name}: снимок по внешнему сигналу сохранён -> {path}")

    # -- main loop ---------------------------------------------------------

    def run(self):
        self.logger.info("Запуск обработки RTSP-потока")
        rtsp_url = self._build_rtsp_url()

        reconnect_count = 0
        while reconnect_count < MAX_RECONNECT_ATTEMPTS:
            if not self._run_capture_session(rtsp_url):
                reconnect_count += 1
                self.logger.info(
                    f"Переподключение ({reconnect_count}/{MAX_RECONNECT_ATTEMPTS}) через {RECONNECT_DELAY_SEC} сек..."
                )
                time.sleep(RECONNECT_DELAY_SEC)

        self.logger.critical("Превышено максимальное количество попыток переподключения. Завершение потока.")

    def _run_capture_session(self, rtsp_url) -> bool:
        """Run a single capture session until the stream drops. Returns False on connection failure."""
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            self.logger.error("Не удалось открыть RTSP-поток. Повторная попытка...")
            cap.release()
            return False

        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        recorder = VideoRecorder(self.camera_dir, self.camera_name, frame_size=(width, height))

        self.logger.info("Поток успешно открыт")
        last_signal_refresh = 0.0

        try:
            while True:
                now = time.time()
                if now - last_signal_refresh >= SIGNAL_REFRESH_INTERVAL_SEC:
                    self._refresh_signals()
                    last_signal_refresh = now

                ret, frame = cap.read()
                if not ret:
                    self.logger.warning("Кадр не получен (ret=False). Поток, возможно, разорван.")
                    return True  # clean drop -> caller will reconnect without counting as a hard failure path

                alert_triggered = self._check_for_alert(frame, now)
                if alert_triggered:
                    self.record_requested = True
                    recorder.mark_for_archive = True
                    recorder.mark_as_alarm = True

                recorder.write(frame)

                if recorder.should_close():
                    if self.record_requested:
                        recorder.mark_for_archive = True
                        signals.clear_signal(self.camera_dir, signals.SIGNAL_RECORD)
                        self.record_requested = False
                    recorder.close_and_finalize()

                if self.photo_requested:
                    self._save_requested_photo(frame)

                self._frames_since_motion_check += 1
        finally:
            if recorder.is_open:
                recorder.close_and_finalize()
            cap.release()
