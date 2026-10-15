import os
import sys
import json
import time
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from ml.inference.terrain_processor import TerrainProcessor
from ml.inference.risk_predictor import SegmentRiskPredictor

OUT_DIR = os.path.join(ROOT_DIR, "data", "risk_features", "processed")
os.makedirs(OUT_DIR, exist_ok=True)

BBOX = {
    "min_lat": 26.10,
    "max_lat": 27.70,
    "min_lon": 91.50,
    "max_lon": 92.80,
}


def generate_corridor_lsi(lat_step: float = 0.025, lon_step: float = 0.025):
    terrain = TerrainProcessor()
    predictor = SegmentRiskPredictor()

    lats = np.arange(BBOX["min_lat"], BBOX["max_lat"] + lat_step / 2, lat_step)
    lons = np.arange(BBOX["min_lon"], BBOX["max_lon"] + lon_step / 2, lon_step)

    cells = []
    features = []

    for lat in lats:
        for lon in lons:
            lat_f = round(float(lat), 4)
            lon_f = round(float(lon), 4)

            t_res = terrain.get_terrain_features(lat_f, lon_f)
            if not t_res["valid"]:
                continue

            pred = predictor.predict_risk(
                lat=lat_f,
                lon=lon_f,
                precip_mm=45.0,
                precip_3d_mm=110.0,
                precip_7d_mm=200.0,
                wind_kmh=15.0,
                month=7,
            )

            prob = pred["disruption_probability"]
            safety = pred["safety_score"]

            if prob < 0.25:
                tier = "LOW"
            elif prob < 0.50:
                tier = "MODERATE"
            elif prob < 0.75:
                tier = "HIGH"
            else:
                tier = "VERY_HIGH"

            cell = {
                "latitude": lat_f,
                "longitude": lon_f,
                "elevation_m": t_res["elevation"],
                "slope_deg": t_res["slope_deg"],
                "tri": t_res["tri"],
                "susceptibility_score": prob,
                "safety_score": safety,
                "hazard_tier": tier,
                "reason_codes": pred["reason_codes"],
            }
            cells.append(cell)

            color_map = {
                "LOW": "#22C55E",
                "MODERATE": "#EAB308",
                "HIGH": "#F97316",
                "VERY_HIGH": "#EF4444",
            }

            feat = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon_f, lat_f],
                },
                "properties": {
                    "elevation_m": t_res["elevation"],
                    "slope_deg": t_res["slope_deg"],
                    "tri": t_res["tri"],
                    "susceptibility_score": prob,
                    "safety_score": safety,
                    "hazard_tier": tier,
                    "color": color_map[tier],
                    "reasons": ", ".join(pred["reason_codes"]),
                },
            }
            features.append(feat)

    terrain.close()
    predictor.close()

    geojson_obj = {
        "type": "FeatureCollection",
        "features": features,
    }

    out_geojson = os.path.join(OUT_DIR, "guwahati_tawang_lsi_grid.geojson")
    with open(out_geojson, "w") as f:
        json.dump(geojson_obj, f, indent=2)

    return out_geojson


if __name__ == "__main__":
    generate_corridor_lsi()
