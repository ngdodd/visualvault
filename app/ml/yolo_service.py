"""
YOLO Object Detection Service

This module provides object detection capabilities using YOLOv8.
It supports multiple model sizes for demonstrating MLOps concepts like:
- Model versioning and registry
- A/B testing different model sizes
- Performance vs accuracy tradeoffs
- Inference metrics tracking
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

import structlog
from PIL import Image

logger = structlog.get_logger()


@dataclass
class Detection:
    """Single object detection result."""
    label: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "bbox": {
                "x1": self.bbox[0],
                "y1": self.bbox[1],
                "x2": self.bbox[2],
                "y2": self.bbox[3],
            },
        }


@dataclass
class DetectionResult:
    """Object detection result with metadata."""
    detections: list[Detection]
    model_name: str
    model_version: str
    inference_time_ms: float
    image_width: int
    image_height: int

    def to_dict(self) -> dict:
        return {
            "detections": [d.to_dict() for d in self.detections],
            "model": {
                "name": self.model_name,
                "version": self.model_version,
            },
            "metrics": {
                "inference_time_ms": round(self.inference_time_ms, 2),
                "num_detections": len(self.detections),
            },
            "image": {
                "width": self.image_width,
                "height": self.image_height,
            },
        }


@dataclass
class ModelMetrics:
    """Tracks inference metrics for MLOps monitoring."""
    total_inferences: int = 0
    total_inference_time_ms: float = 0.0
    total_detections: int = 0

    def record(self, inference_time_ms: float, num_detections: int):
        self.total_inferences += 1
        self.total_inference_time_ms += inference_time_ms
        self.total_detections += num_detections

    @property
    def avg_inference_time_ms(self) -> float:
        if self.total_inferences == 0:
            return 0.0
        return self.total_inference_time_ms / self.total_inferences

    @property
    def avg_detections_per_image(self) -> float:
        if self.total_inferences == 0:
            return 0.0
        return self.total_detections / self.total_inferences

    def to_dict(self) -> dict:
        return {
            "total_inferences": self.total_inferences,
            "avg_inference_time_ms": round(self.avg_inference_time_ms, 2),
            "avg_detections_per_image": round(self.avg_detections_per_image, 2),
            "total_detections": self.total_detections,
        }


# Available model sizes with their characteristics
MODEL_VARIANTS = {
    "yolov8n": {
        "name": "YOLOv8 Nano",
        "description": "Fastest, lowest accuracy",
        "size_mb": 6,
        "speed": "fastest",
    },
    "yolov8s": {
        "name": "YOLOv8 Small",
        "description": "Fast with good accuracy",
        "size_mb": 22,
        "speed": "fast",
    },
    "yolov8m": {
        "name": "YOLOv8 Medium",
        "description": "Balanced speed and accuracy",
        "size_mb": 52,
        "speed": "medium",
    },
    "yolov8l": {
        "name": "YOLOv8 Large",
        "description": "High accuracy, slower",
        "size_mb": 87,
        "speed": "slow",
    },
}

DEFAULT_MODEL = "yolov8n"


class YOLOService:
    """
    YOLO object detection service with support for multiple model versions.

    This service demonstrates MLOps patterns:
    - Model versioning: Load different YOLO model sizes
    - Metrics tracking: Record inference times and detection counts
    - Lazy loading: Models loaded on first use
    """

    def __init__(self):
        self._models: dict = {}  # Cache loaded models
        self._metrics: dict[str, ModelMetrics] = {}  # Metrics per model
        self._initialized = False

    def _ensure_model_loaded(self, model_name: str) -> None:
        """Load a model if not already cached."""
        if model_name in self._models:
            return

        if model_name not in MODEL_VARIANTS:
            raise ValueError(f"Unknown model: {model_name}. Available: {list(MODEL_VARIANTS.keys())}")

        logger.info("Loading YOLO model", model=model_name)
        start = time.time()

        from ultralytics import YOLO

        # Load the model (downloads automatically if not present)
        self._models[model_name] = YOLO(f"{model_name}.pt")
        self._metrics[model_name] = ModelMetrics()

        load_time = (time.time() - start) * 1000
        logger.info("YOLO model loaded", model=model_name, load_time_ms=round(load_time, 2))
        self._initialized = True

    def detect(
        self,
        image: Image.Image | BinaryIO,
        model_name: str = DEFAULT_MODEL,
        confidence_threshold: float = 0.25,
        max_detections: int = 100,
    ) -> DetectionResult:
        """
        Run object detection on an image.

        Args:
            image: PIL Image or file-like object
            model_name: Which YOLO model to use (yolov8n, yolov8s, yolov8m, yolov8l)
            confidence_threshold: Minimum confidence for detections (0-1)
            max_detections: Maximum number of detections to return

        Returns:
            DetectionResult with bounding boxes and metadata
        """
        self._ensure_model_loaded(model_name)
        model = self._models[model_name]

        # Handle file-like objects
        if not isinstance(image, Image.Image):
            image = Image.open(image)

        if image.mode != "RGB":
            image = image.convert("RGB")

        width, height = image.size

        # Run inference with timing
        start = time.time()
        results = model(image, conf=confidence_threshold, verbose=False)
        inference_time = (time.time() - start) * 1000

        # Parse results
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for i in range(len(boxes)):
                if len(detections) >= max_detections:
                    break

                box = boxes[i]
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = model.names[cls_id]

                detections.append(Detection(
                    label=label,
                    confidence=conf,
                    bbox=(int(x1), int(y1), int(x2), int(y2)),
                ))

        # Sort by confidence
        detections.sort(key=lambda d: d.confidence, reverse=True)

        # Record metrics
        self._metrics[model_name].record(inference_time, len(detections))

        return DetectionResult(
            detections=detections,
            model_name=MODEL_VARIANTS[model_name]["name"],
            model_version=model_name,
            inference_time_ms=inference_time,
            image_width=width,
            image_height=height,
        )

    def get_available_models(self) -> dict:
        """Get information about available models."""
        return {
            name: {
                **info,
                "loaded": name in self._models,
            }
            for name, info in MODEL_VARIANTS.items()
        }

    def get_metrics(self, model_name: str | None = None) -> dict:
        """
        Get inference metrics for MLOps monitoring.

        Args:
            model_name: Specific model to get metrics for, or None for all

        Returns:
            Metrics dictionary
        """
        if model_name:
            if model_name not in self._metrics:
                return {"error": f"No metrics for model: {model_name}"}
            return {model_name: self._metrics[model_name].to_dict()}

        return {
            name: metrics.to_dict()
            for name, metrics in self._metrics.items()
        }

    def reset_metrics(self, model_name: str | None = None) -> None:
        """Reset metrics for a model or all models."""
        if model_name:
            if model_name in self._metrics:
                self._metrics[model_name] = ModelMetrics()
        else:
            for name in self._metrics:
                self._metrics[name] = ModelMetrics()


# Global singleton instance
_yolo_service: YOLOService | None = None


def get_yolo_service() -> YOLOService:
    """Get or create the YOLO service singleton."""
    global _yolo_service
    if _yolo_service is None:
        _yolo_service = YOLOService()
    return _yolo_service


def init_yolo_service(model_name: str = DEFAULT_MODEL) -> YOLOService:
    """Initialize YOLO service and pre-load a model."""
    service = get_yolo_service()
    service._ensure_model_loaded(model_name)
    return service
