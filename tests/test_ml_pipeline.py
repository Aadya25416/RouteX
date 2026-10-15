import os
import sys
import unittest
import numpy as np
from PIL import Image, ImageDraw

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from ml.inference.terrain_processor import TerrainProcessor
from ml.inference.risk_predictor import SegmentRiskPredictor
from ml.inference.delay_predictor import MountainDelayPredictor
from ml.inference.road_extractor import RoadExtractor
from ml.inference.unified_risk_pipeline import RouteXUnifiedMLPipeline


class TestRouteXMLPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terrain_proc = TerrainProcessor()
        cls.risk_pred = SegmentRiskPredictor()
        cls.delay_pred = MountainDelayPredictor()
        cls.unified_pipe = RouteXUnifiedMLPipeline()

    @classmethod
    def tearDownClass(cls):
        cls.terrain_proc.close()
        cls.risk_pred.close()
        cls.delay_pred.close()
        cls.unified_pipe.close()

    def test_terrain_processor_horn_slope(self):
        if not os.path.exists(self.terrain_proc.west_dem) and not os.path.exists(self.terrain_proc.east_dem):
            self.skipTest("DEM raster files not downloaded on this machine")
        guw = self.terrain_proc.get_terrain_features(26.185, 91.750)
        self.assertTrue(20.0 <= guw["elevation"] <= 250.0)
        self.assertTrue(guw["slope_deg"] < 15.0)

        sela = self.terrain_proc.get_terrain_features(27.504, 92.102)
        self.assertTrue(sela["elevation"] > 3500.0)
        self.assertTrue(sela["slope_deg"] > 10.0)
        self.assertTrue(sela["tri"] > 3.0)

    def test_landslide_risk_prediction(self):
        safe_res = self.risk_pred.predict_risk(
            lat=26.185, lon=91.750, precip_mm=0.0, precip_3d_mm=0.0, precip_7d_mm=0.0, month=1
        )
        self.assertGreaterEqual(safe_res["safety_score"], 75.0)
        self.assertLess(safe_res["disruption_probability"], 0.25)

        hazard_res = self.risk_pred.predict_risk(
            lat=27.586, lon=91.859, precip_mm=75.0, precip_3d_mm=210.0, precip_7d_mm=380.0, month=7
        )
        self.assertGreater(hazard_res["disruption_probability"], 0.60)
        self.assertLess(hazard_res["safety_score"], 50.0)
        self.assertTrue(any("SLOPE" in r or "RAIN" in r for r in hazard_res["reason_codes"]))

    def test_mountain_delay_predictor(self):
        if not os.path.exists(self.delay_pred.terrain.west_dem) and not os.path.exists(self.delay_pred.terrain.east_dem):
            self.skipTest("DEM raster files not downloaded on this machine")
        res_dry = self.delay_pred.predict_segment_speed(
            lat=26.185, lon=91.750, road_class=1, base_speed_kmh=60.0, rain_mm=0.0, month=1
        )
        self.assertGreaterEqual(res_dry["degradation_factor"], 0.85)
        self.assertLessEqual(res_dry["delay_multiplier"], 1.25)

        res_monsoon = self.delay_pred.predict_segment_speed(
            lat=27.504, lon=92.102, road_class=1, base_speed_kmh=60.0, rain_mm=55.0, month=7
        )
        self.assertLessEqual(res_monsoon["degradation_factor"], 0.40)
        self.assertGreaterEqual(res_monsoon["delay_multiplier"], 2.5)
        self.assertIn("EXTREME_MONSOON_RAINFALL", res_monsoon["delay_reasons"])

    def test_road_extractor_inference(self):
        extractor = RoadExtractor()
        test_img = Image.new("RGB", (256, 256), color=(50, 80, 45))
        draw = ImageDraw.Draw(test_img)
        draw.line([(20, 20), (128, 128), (230, 230)], fill=(180, 180, 185), width=8)

        res = extractor.extract_roads(test_img, threshold=0.35)
        self.assertIn("probability_map", res)
        self.assertIn("binary_mask", res)
        self.assertIn("skeleton", res)
        self.assertGreater(res["road_pixel_count"], 0)
        self.assertGreater(np.sum(res["skeleton"]), 0)

    def test_unified_corridor_evaluation(self):
        corridor = [
            (26.185, 91.750),
            (26.650, 92.800),
            (27.010, 92.650),
            (27.504, 92.102),
        ]
        summary = self.unified_pipe.evaluate_corridor(
            waypoints=corridor,
            road_class=1,
            rain_mm=40.0,
            month=7,
        )

        self.assertGreater(summary["total_distance_km"], 100.0)
        self.assertGreater(summary["degraded_travel_time_h"], summary["nominal_travel_time_h"])
        self.assertGreater(summary["added_weather_delay_h"], 0.0)
        self.assertLess(summary["worst_safety_score"], 80.0)
        self.assertEqual(len(summary["segments"]), 4)


if __name__ == "__main__":
    unittest.main()
