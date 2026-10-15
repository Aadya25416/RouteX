import os
import json
import numpy as np
import xgboost as xgb

try:
    from ml.inference.terrain_processor import TerrainProcessor
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from ml.inference.terrain_processor import TerrainProcessor

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(ROOT_DIR, "ml", "models", "xgboost", "travel_delay_xgboost.json")
META_PATH = os.path.join(ROOT_DIR, "ml", "models", "xgboost", "travel_delay_metadata.json")

CLASS_BASE_SPEEDS = {
    0: 75.0,
    1: 60.0,
    2: 45.0,
    3: 35.0,
    4: 25.0,
}


class MountainDelayPredictor:
    def __init__(self, weights=MODEL_PATH, meta=META_PATH):
        self.weights = weights
        self.meta = meta
        self.reg = None
        self.meta_dict = {}
        self.terrain = TerrainProcessor()
        self._load()

    def _load(self):
        if not os.path.exists(self.weights):
            raise FileNotFoundError(f"Missing weights: {self.weights}")
        self.reg = xgb.XGBRegressor()
        self.reg.load_model(self.weights)
        if os.path.exists(self.meta):
            with open(self.meta, "r") as f:
                self.meta_dict = json.load(f)

    def close(self):
        if self.terrain:
            self.terrain.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def predict_segment_speed(
        self,
        lat: float,
        lon: float,
        road_class: int = 1,
        base_speed_kmh: float = None,
        rain_mm: float = 0.0,
        month: int = 7,
    ) -> dict:
        if base_speed_kmh is None:
            base_speed_kmh = CLASS_BASE_SPEEDS.get(road_class, 45.0)

        t_res = self.terrain.get_terrain_features(lat, lon)
        elev = t_res["elevation"]
        slope = t_res["slope_deg"]
        tri = t_res["tri"]

        monsoon = 1 if (month in (6, 7, 8, 9) or rain_mm > 15.0) else 0

        vec = np.array([[
            float(road_class),
            float(base_speed_kmh),
            float(elev),
            float(slope),
            float(tri),
            float(rain_mm),
            float(monsoon),
        ]], dtype=np.float32)

        raw_deg = float(self.reg.predict(vec)[0])
        deg = float(np.clip(raw_deg, 0.20, 1.00))

        v_eff = round(base_speed_kmh * deg, 1)
        delay_factor = round(1.0 / deg, 2)

        reasons = []
        if slope > 20.0:
            reasons.append("STEEP_MOUNTAIN_GRADE")
        if rain_mm > 40.0:
            reasons.append("EXTREME_MONSOON_RAINFALL")
        elif rain_mm > 15.0:
            reasons.append("MODERATE_RAINFALL_SLIP")
        if elev > 2500.0:
            reasons.append("HIGH_ALTITUDE_PASS_HAZARD")
        if tri > 15.0:
            reasons.append("RUGGED_TERRAIN_ROUGHNESS")

        return {
            "latitude": lat,
            "longitude": lon,
            "road_class": road_class,
            "base_speed_kmh": base_speed_kmh,
            "degradation_factor": round(deg, 3),
            "effective_speed_kmh": v_eff,
            "delay_multiplier": delay_factor,
            "delay_reasons": reasons,
            "terrain_metrics": {
                "elevation_m": round(elev, 1),
                "slope_deg": round(slope, 2),
                "tri": round(tri, 2),
            },
        }
