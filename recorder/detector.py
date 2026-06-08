"""YOLOv8-based object detector used to confirm motion-triggered alerts."""
from dataclasses import dataclass

import cv2
import numpy as np
from ultralytics import YOLO

from logger_setup import get_logger

# Class ids in the COCO model that we care about (people, bicycle, car, motorcycle).
LEGAL_CLASSES = (0, 1, 2, 3)

_COLORS = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255),
    (255, 0, 255), (192, 192, 192), (128, 128, 128), (128, 0, 0), (128, 128, 0),
    (0, 128, 0), (128, 0, 128), (0, 128, 128), (0, 0, 128), (72, 61, 139),
    (47, 79, 79), (47, 79, 47), (0, 206, 209), (148, 0, 211), (255, 20, 147),
]


@dataclass
class Detection:
    image: "np.ndarray"
    class_name: str
    area: int
    confidence: float


class AIdetector:
    """Wraps a YOLOv8 model and filters detections to a relevant subset of classes/sizes."""

    def __init__(self, conf=0.2, min_area=500, model_path="yolov8n.pt"):
        self.model = YOLO(model_path)
        self.legal_classes = LEGAL_CLASSES
        self.conf = conf
        self.min_area = min_area
        self.logger = get_logger("detector")
        self.logger.info("Инициализация AI-детектора")

    def process_image(self, image):
        """Run detection on a frame; return a Detection for the first relevant object found, or None."""
        try:
            results = self.model(image, verbose=False, conf=self.conf)[0]
        except Exception:
            self.logger.exception("Ошибка при инференсе модели")
            return None

        orig_img = results.orig_img
        classes = results.boxes.cls.cpu().numpy()
        boxes = results.boxes.xyxy.cpu().numpy().astype(np.int32)
        confs = results.boxes.conf.cpu().numpy()
        class_names = results.names

        for class_id, box, conf in zip(classes, boxes, confs):
            class_id_int = int(class_id)
            if class_id_int not in self.legal_classes:
                return None

            x1, y1, x2, y2 = box
            area = int((x2 - x1) * (y2 - y1))
            if area < self.min_area:
                return None

            class_name = class_names[class_id_int]
            color = _COLORS[class_id_int % len(_COLORS)]

            annotated = cv2.rectangle(orig_img, (x1, y1), (x2, y2), color, 1)
            annotated = cv2.putText(annotated, class_name, (x1, y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            self.logger.info(f"Обнаружен объект: {class_name}, площадь={area}, уверенность={conf:.2f}")
            return Detection(image=annotated, class_name=class_name, area=area, confidence=float(conf))

        return None
