"""Sentinel-file based cross-process signalling between the control surface and camera processes.

Each camera has its own folder under Resources/<camera_name>/. A signal is "set" by creating
an empty file with a well-known name in that folder, and "cleared" by deleting it.
"""
import os

SIGNAL_PHOTO = "__tmp_make_photo"
SIGNAL_ALARM = "__set_alarm"
SIGNAL_RECORD = "__tmp_record_start"

ALL_SIGNALS = (SIGNAL_PHOTO, SIGNAL_ALARM, SIGNAL_RECORD)


def _path(camera_dir, signal_name):
    return os.path.join(camera_dir, signal_name)


def has_signal(camera_dir, signal_name):
    return os.path.exists(_path(camera_dir, signal_name))


def set_signal(camera_dir, signal_name):
    path = _path(camera_dir, signal_name)
    if not os.path.exists(path):
        open(path, "w").close()


def clear_signal(camera_dir, signal_name):
    path = _path(camera_dir, signal_name)
    if os.path.exists(path):
        os.remove(path)
