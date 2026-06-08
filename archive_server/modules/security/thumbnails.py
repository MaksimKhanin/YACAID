"""Generates small JPEG thumbnails for media grid views (mobile-friendly fast loading)."""
from pathlib import Path

import cv2

THUMB_MAX_DIM = 320
THUMB_SUFFIX = "_thumb.jpg"


def thumbnail_path_for(media_path: Path) -> Path:
    return media_path.with_name(media_path.stem + THUMB_SUFFIX)


def _resize_keep_aspect(image, max_dim):
    h, w = image.shape[:2]
    scale = max_dim / max(h, w)
    if scale >= 1:
        return image
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def generate_thumbnail(media_path: Path, kind: str) -> Path | None:
    """Generate a thumbnail for a photo or the first frame of a video. Returns the thumb path or None."""
    thumb_path = thumbnail_path_for(media_path)

    if kind == "photo":
        image = cv2.imread(str(media_path))
    else:
        cap = cv2.VideoCapture(str(media_path))
        ok, image = cap.read()
        cap.release()
        if not ok:
            image = None

    if image is None:
        return None

    thumb = _resize_keep_aspect(image, THUMB_MAX_DIM)
    cv2.imwrite(str(thumb_path), thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return thumb_path
