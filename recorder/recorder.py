"""Rolling-chunk video writer with the recorder's filename-suffix conventions.

Filename suffixes (consumed by archive_sync / the archive server's filename parser):
  ..._video.mp4              chunk still being written / not yet finalized
  ..._video_done.mp4         finished chunk, no special handling requested
  ..._video_done_post.mp4    finished chunk that should be pushed to the archive server
  ..._video_done_post_alarm.mp4   same, plus flagged as an alert (AI-confirmed detection)
"""
import os
import time
from datetime import datetime

import cv2

from logger_setup import get_logger

DONE_SUFFIX = "_done"
POST_SUFFIX = "_post"
ALARM_SUFFIX = "_alarm"

FOURCC_MP4 = 0x7634706d  # 'mp4v'


class VideoRecorder:
    """Writes rolling video chunks to disk and renames finished chunks per the naming convention."""

    def __init__(self, camera_dir, camera_name, frame_size, target_fps=15,
                 chunk_duration_sec=20, extra_frames_to_save=20 * 15):
        self.camera_dir = camera_dir
        self.camera_name = camera_name
        self.frame_size = frame_size  # (width, height)
        self.target_fps = target_fps
        self.chunk_duration_sec = chunk_duration_sec
        self.extra_frames_to_save = extra_frames_to_save

        self.logger = get_logger(f"recorder_{camera_name}")

        self._writer = None
        self._path = None
        self._chunk_start_time = None
        self._frames_written = 0

        # Flags set by the caller before a chunk closes, consumed on finalize.
        self.mark_for_archive = False
        self.mark_as_alarm = False

    @property
    def is_open(self):
        return self._writer is not None

    def _new_chunk_path(self):
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return os.path.join(self.camera_dir, f"{now}_{self.camera_name}_video.mp4")

    def open_chunk(self):
        self._path = self._new_chunk_path()
        w, h = self.frame_size
        self._writer = cv2.VideoWriter(self._path, FOURCC_MP4, float(self.target_fps), (int(w), int(h)))
        self._chunk_start_time = time.time()
        self._frames_written = 0

    def write(self, frame):
        if self._writer is None:
            self.open_chunk()
        self._writer.write(frame)
        self._frames_written += 1

    def should_close(self) -> bool:
        if self._writer is None:
            return False
        elapsed = time.time() - self._chunk_start_time
        if elapsed <= self.chunk_duration_sec:
            return False
        return self._frames_written >= self.extra_frames_to_save

    def close_and_finalize(self):
        """Release the writer and rename the finished chunk according to pending flags."""
        if self._writer is None:
            return None

        self._writer.release()
        self._writer = None

        name_without_ext, ext = os.path.splitext(self._path)
        new_name = name_without_ext + DONE_SUFFIX

        if self.mark_for_archive:
            new_name += POST_SUFFIX
            if self.mark_as_alarm:
                new_name += ALARM_SUFFIX

        new_path = new_name + ext
        os.rename(self._path, new_path)
        self.logger.debug(f"Файл переименован: {self._path} -> {new_path}")

        finished_path = new_path
        self._path = None
        self._chunk_start_time = None
        self._frames_written = 0
        self.mark_for_archive = False
        self.mark_as_alarm = False

        return finished_path
