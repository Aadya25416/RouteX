import os
import sys
import json
import math
from typing import List, Dict, Any, Tuple
from shapely.geometry import Point, shape

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from ml.inference.terrain_processor import TerrainProcessor
from ml.inference.risk_predictor import SegmentRiskPredictor
from ml.inference.delay_predictor import MountainDelayPredictor

FLOOD_FILE = os.path.join(
    ROOT_DIR, "data", "satellite", "sentinel1", "assam_flood_2024_polygons.geojson"
)


class RouteXUnifiedMLPipeline:
    def __init__(self, flood_geojson=FLOOD_FILE):
        self.risk_predictor = SegmentRiskPredictor()
        self.delay_predictor = MountainDelayPredictor()
        self.flood_polygons = []
        self._load_floods(flood_geojson)

    def _load_floods(self, path: str):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                for ft in data.get("features", []):
                    g = ft.get("geometry")
                    if g:
                        self.flood_polygons.append(shape(g))
            except Exception:
                pass

    def close(self):
        if self.risk_predictor:
            self.risk_predictor.close()
        if self.delay_predictor:
            self.delay_predictor.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def is_point_flooded(self, lat: float, lon: float) -> bool:
        pt = Point(lon, lat)
        for poly in self.flood_polygons:
            if poly.contains(pt):
                return True
        return False

    def evaluate_point(
        self,
        lat: float,
        lon: float,
        road_class: int = 1,
        base_speed_kmh: float = None,
        rain_mm: float = 0.0,
        precip_3d_mm: float = 0.0,
        precip_7d_mm: float = 0.0,
        wind_kmh: float = 12.0,
        month: int = 7,
    ) -> Dict[str, Any]:
        risk_res = self.risk_predictor.predict_risk(
            lat=lat,
            lon=lon,
            precip_mm=rain_mm,
            precip_3d_mm=precip_3d_mm,
            precip_7d_mm=precip_7d_mm,
            wind_kmh=wind_kmh,
            month=month,
        )

        delay_res = self.delay_predictor.predict_segment_speed(
            lat=lat,
            lon=lon,
            road_class=road_class,
            base_speed_kmh=base_speed_kmh,
            rain_mm=rain_mm,
            month=month,
        )

        flooded = self.is_point_flooded(lat, lon)

        reasons = list(risk_res.get("reason_codes", []))
        for r in delay_res.get("delay_reasons", []):
            if r not in reasons:
                reasons.append(r)

        prob = risk_res["disruption_probability"]
        safety = risk_res["safety_score"]
        v_eff = delay_res["effective_speed_kmh"]
        delay_mult = delay_res["delay_multiplier"]

        if flooded:
            reasons.insert(0, "SAR_FLOOD_SUBMERGENCE")
            prob = max(0.98, prob)
            safety = min(2.0, safety)
            v_eff = 0.0
            delay_mult = 99.0
            status_val = "BLOCKED"
        elif prob >= 0.80 or safety < 30.0:
            status_val = "BLOCKED"
        elif prob >= 0.50 or safety < 60.0:
            status_val = "AT_RISK"
        elif prob >= 0.25 or safety < 80.0:
            status_val = "RESTRICTED"
        else:
            status_val = "VERIFIED_SAFE"

        return {
            "latitude": lat,
            "longitude": lon,
            "status": status_val,
            "safety_score": round(safety, 1),
            "disruption_probability": round(prob, 4),
            "confidence": risk_res["confidence"],
            "effective_speed_kmh": round(v_eff, 1),
            "base_speed_kmh": delay_res["base_speed_kmh"],
            "delay_multiplier": round(delay_mult, 2),
            "is_flooded": flooded,
            "reasons": reasons,
            "terrain": risk_res.get("terrain", {}),
        }

    def evaluate_corridor(
        self,
        waypoints: List[Tuple[float, float]],
        road_class: int = 1,
        rain_mm: float = 0.0,
        month: int = 7,
    ) -> Dict[str, Any]:
        evaluated = []
        min_safety = 100.0
        max_delay = 1.0
        t_nom = 0.0
        t_deg = 0.0
        dist_km = 0.0
        n_blocked = 0
        n_at_risk = 0

        for i in range(len(waypoints)):
            lat, lon = waypoints[i]
            res = self.evaluate_point(lat, lon, road_class=road_class, rain_mm=rain_mm, month=month)
            evaluated.append(res)

            if res["status"] == "BLOCKED":
                n_blocked += 1
            elif res["status"] == "AT_RISK":
                n_at_risk += 1

            min_safety = min(min_safety, res["safety_score"])
            max_delay = max(max_delay, res["delay_multiplier"])

            if i > 0:
                p_lat, p_lon = waypoints[i - 1]
                dlat = math.radians(lat - p_lat)
                dlon = math.radians(lon - p_lon)
                a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(p_lat)) * math.cos(math.radians(lat)) * math.sin(dlon / 2) ** 2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                step_km = 6371.0 * c
                dist_km += step_km

                base_v = res["base_speed_kmh"]
                eff_v = max(5.0, res["effective_speed_kmh"])

                t_nom += step_km / base_v
                t_deg += step_km / eff_v

        corridor_status = "BLOCKED" if n_blocked > 0 else ("AT_RISK" if n_at_risk > 0 else "VERIFIED_SAFE")

        return {
            "total_distance_km": round(dist_km, 1),
            "nominal_travel_time_h": round(t_nom, 2),
            "degraded_travel_time_h": round(t_deg, 2),
            "added_weather_delay_h": round(max(0.0, t_deg - t_nom), 2),
            "worst_safety_score": round(min_safety, 1),
            "max_delay_multiplier": round(max_delay, 2),
            "overall_corridor_status": corridor_status,
            "blocked_segments_count": n_blocked,
            "at_risk_segments_count": n_at_risk,
            "waypoints_count": len(waypoints),
            "segments": evaluated,
        }

    def export_corridor_geojson(self, corridor_summary: Dict[str, Any], out_path: str):
        features = []
        segments = corridor_summary.get("segments", [])

        color_lut = {
            "VERIFIED_SAFE": "#10B981",
            "RESTRICTED": "#FBBF24",
            "AT_RISK": "#F97316",
            "BLOCKED": "#EF4444",
        }

        for seg in segments:
            props = {
                "status": seg["status"],
                "color": color_lut.get(seg["status"], "#6B7280"),
                "safety_score": seg["safety_score"],
                "effective_speed_kmh": seg["effective_speed_kmh"],
                "delay_multiplier": seg["delay_multiplier"],
                "elevation_m": seg.get("terrain", {}).get("elevation_m", 0.0),
                "slope_deg": seg.get("terrain", {}).get("slope_deg", 0.0),
                "reasons": ", ".join(seg["reasons"]) if seg["reasons"] else "Nominal conditions",
            }
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [seg["longitude"], seg["latitude"]],
                },
                "properties": props,
            })

        if len(segments) >= 2:
            coords = [[s["longitude"], s["latitude"]] for s in segments]
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords,
                },
                "properties": {
                    "total_distance_km": corridor_summary["total_distance_km"],
                    "nominal_time_h": corridor_summary["nominal_travel_time_h"],
                    "weather_delayed_time_h": corridor_summary["degraded_travel_time_h"],
                    "overall_status": corridor_summary["overall_corridor_status"],
                },
            })

        fc = {"type": "FeatureCollection", "features": features}
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(fc, f, indent=2)
