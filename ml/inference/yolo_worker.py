import os
import sys
import logging
from typing import Dict, Any
from PIL import Image
import io

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

try:
    from backend.config import get_settings
    _settings = get_settings()
    DEFAULT_WEIGHTS_PATH = os.path.join(ROOT_DIR, _settings.ML_YOLO_WEIGHTS_PATH)
    DEFAULT_WORKER_ID = _settings.ML_WORKER_ID
except Exception:
    DEFAULT_WEIGHTS_PATH = os.path.join(ROOT_DIR, "ml", "models", "best.pt")
    DEFAULT_WORKER_ID = "worker-routex-01"

logger = logging.getLogger(__name__)

DEFAULT_CLASSES = {
    0: "pothole",
    1: "longitudinal_crack",
    2: "transverse_crack",
    3: "alligator_crack",
    4: "landslide_debris",
    5: "flood_waterlogging",
}


class YOLORoadDamageWorker:
    def __init__(
        self,
        worker_id: str = DEFAULT_WORKER_ID,
        weights_file: str = DEFAULT_WEIGHTS_PATH,
        device: str = "cpu",
    ):
        self.worker_id = worker_id
        self.weights_file = weights_file
        self.device = device
        self.model = None
        self.classes = dict(DEFAULT_CLASSES)
        self.load_error = None
        self._load()

    def _load(self):
        # Fall back to alternative known locations if default does not exist
        candidate_paths = [
            self.weights_file,
            os.path.join(ROOT_DIR, "ml", "models", "best.pt"),
            os.path.join(ROOT_DIR, "ml", "models", "yolo26", "best_road_damage.pt"),
        ]
        target_path = None
        for p in candidate_paths:
            if p and os.path.exists(p):
                target_path = p
                break

        if target_path:
            try:
                from ultralytics import YOLO
                self.model = YOLO(target_path)
                self.weights_file = target_path
                if hasattr(self.model, "names") and isinstance(self.model.names, dict):
                    self.classes = {int(k): str(v) for k, v in self.model.names.items()}
                logger.info(f"YOLO road damage model loaded successfully from {target_path}")
            except Exception as e:
                self.load_error = f"Failed to initialize YOLO model from '{target_path}': {e}"
                logger.warning(self.load_error)
                self.model = None
        else:
            self.load_error = f"YOLO model weights file not found. Checked: {candidate_paths}"
            logger.warning(self.load_error)
            self.model = None

    def detect_damage(self, raw_bytes: bytes) -> Dict[str, Any]:
        """
        Executes YOLO road damage detection on raw image bytes.
        Returns validated bounding boxes, detection classes, confidences, and model metadata.
        Never fabricates detections when inference or model is unavailable.
        """
        if not raw_bytes or len(raw_bytes) == 0:
            return {
                "status": "FAILED",
                "detection_class": None,
                "confidence": 0.0,
                "metadata": {
                    "error_code": "EMPTY_PAYLOAD",
                    "model": "yolo_road_damage",
                },
                "error": "Empty or zero-byte image payload received.",
            }

        try:
            img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        except Exception as e:
            return {
                "status": "FAILED",
                "detection_class": None,
                "confidence": 0.0,
                "metadata": {
                    "error_code": "CORRUPT_IMAGE",
                    "model": "yolo_road_damage",
                },
                "error": f"Invalid or unreadable image bytes: {str(e)}",
            }

        if self.model is None:
            return {
                "status": "FAILED",
                "detection_class": None,
                "confidence": 0.0,
                "metadata": {
                    "error_code": "MODEL_UNAVAILABLE",
                    "model": "yolo_road_damage",
                },
                "error": self.load_error or "YOLO model weights or runtime dependencies are unavailable.",
            }

        try:
            res = self.model(img, device=self.device, verbose=False)
            boxes = []
            best_cls = None
            max_c = 0.0

            for r in res:
                if not hasattr(r, "boxes") or r.boxes is None:
                    continue
                for b in r.boxes:
                    c_id = int(b.cls.item())
                    score = float(b.conf.item())
                    lbl = self.classes.get(c_id, f"CLASS_{c_id}")
                    pts = [round(float(x), 1) for x in b.xyxy[0].tolist()]
                    boxes.append({
                        "class": lbl,
                        "class_id": c_id,
                        "confidence": round(score, 3),
                        "bbox_xyxy": pts,
                    })
                    if score > max_c:
                        max_c = score
                        best_cls = lbl

            return {
                "status": "COMPLETED",
                "detection_class": best_cls or "NO_DAMAGE_DETECTED",
                "confidence": round(max_c, 3),
                "metadata": {
                    "total_detections": len(boxes),
                    "detections": boxes,
                    "model": "yolo_road_damage",
                    "model_version": getattr(self.model, "ckpt_path", "yolov8n-rdd"),
                },
                "error": None,
            }
        except Exception as exc:
            return {
                "status": "FAILED",
                "detection_class": None,
                "confidence": 0.0,
                "metadata": {
                    "error_code": "INFERENCE_ERROR",
                    "model": "yolo_road_damage",
                },
                "error": f"Inference execution failed: {str(exc)}",
            }
