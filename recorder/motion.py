"""Background-subtraction based motion detection for a single camera stream."""
import cv2


class MotionDetector:
    """Wraps an MOG2 background subtractor and reports whether a frame contains significant motion."""

    def __init__(self, motion_threshold=10000, history=500, var_threshold=16, detect_shadows=False):
        self.motion_threshold = motion_threshold
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=var_threshold,
            detectShadows=detect_shadows,
        )

    def motion_pixels(self, frame) -> int:
        """Return the count of foreground pixels detected in the frame (updates internal model)."""
        fg_mask = self._subtractor.apply(frame.copy())
        return cv2.countNonZero(fg_mask)

    def has_motion(self, frame) -> bool:
        return self.motion_pixels(frame) > self.motion_threshold
