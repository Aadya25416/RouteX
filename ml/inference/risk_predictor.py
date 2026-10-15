import os
import json
import xgboost as xgb
import numpy as np

try:
    from ml.inference.terrain_processor import TerrainProcessor
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from ml.inference.terrain_processor import TerrainProcessor

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEIGHTS_PATH = os.path.join(ROOT_DIR, "ml", "models", "xgboost", "landslide_risk_xgboost.json")
META_PATH = os.path.join(ROOT_DIR, "ml", "models", "xgboost", "model_metadata.json")


class SegmentRiskPredictor:
    def __init__(self, model_file=WEIGHTS_PATH, meta_file=META_PATH):
        self.model_file = model_file
        self.meta_file = meta_file
        self.clf = None
        self.meta = {}
        self.terrain = TerrainProcessor()
        self._load()

    def _load(self):
        if not os.path.exists(self.model_file):
            raise FileNotFoundError(f"Missing weights: {self.model_file}")
        self.clf = xgb.XGBClassifier()
        self.clf.load_model(self.model_file)
        if os.path.exists(self.meta_file):
            with open(self.meta_file, "r") as f:
                self.meta = json.load(f)

    def close(self):
        if self.terrain:
            self.terrain.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def predict_risk(
        self,
        lat: float,
        lon: float,
        precip_mm: float = 0.0,
        precip_3d_mm: float = 0.0,
        precip_7d_mm: float = 0.0,
        wind_kmh: float = 12.0,
        month: int = 7,
    ) -> dict:
        t_data = self.terrain.get_terrain_features(lat, lon)
        elev = t_data["elevation"]
        slope = t_data["slope_deg"]
        aspect = t_data["aspect_deg"]
        tri = t_data["tri"]
        monsoon = 1 if month in (5, 6, 7, 8, 9) else 0

        vec = np.array([
            [elev, slope, aspect, tri, precip_mm, precip_3d_mm, precip_7d_mm, wind_kmh, month, monsoon]
        ], dtype=np.float32)

        prob = float(self.clf.predict_proba(vec)[0][1])
        safety = max(0.0, min(100.0, round(100.0 * (1.0 - prob), 1)))
        disruption_prob = max(0.0, min(1.0, round(prob, 4)))

        flags = []
        if slope >= 25.0:
            flags.append("STEEP_SLOPE_HAZARD")
        elif slope >= 15.0:
            flags.append("MODERATE_SLOPE")

        if precip_3d_mm >= 75.0:
            flags.append("SEVERE_ANTECEDENT_RAINFALL")
        elif precip_3d_mm >= 35.0:
            flags.append("MODERATE_SOIL_SATURATION")

        if precip_mm >= 50.0:
            flags.append("TORRENTIAL_PRECIPITATION")
        elif precip_mm >= 25.0:
            flags.append("HEAVY_RAINFALL")

        if monsoon and disruption_prob >= 0.5:
            flags.append("MONSOON_SURFACE_DESTABILIZATION")

        if tri >= 8.0:
            flags.append("RUGGED_TOPOGRAPHY")

        if not flags:
            flags.append("NOMINAL_CONDITIONS")

        return {
            "disruption_probability": disruption_prob,
            "safety_score": safety,
            "confidence": 0.95,
            "model_name": "xgboost_ner_landslide_risk",
            "model_version": self.meta.get("model_version", "1.1.0"),
            "reason_codes": flags,
            "terrain": {
                "elevation_m": elev,
                "slope_deg": slope,
                "aspect_deg": aspect,
                "tri": tri,
            }
        }
