import os
import json
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
from scipy import ndimage
import rasterio
from shapely.geometry import Polygon, Point, MultiPolygon, mapping, shape
from shapely.ops import unary_union

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
S1_DIR = os.path.join(ROOT_DIR, "data", "satellite", "sentinel1")
GEOJSON_OUT = os.path.join(S1_DIR, "assam_flood_2024_polygons.geojson")


class SARFloodProcessor:
    def __init__(self, s1_path=S1_DIR):
        self.s1_path = s1_path
        self.scenes = []
        self.polys = []
        self._union = None
        self._scan()
        self._init_polygons()

    def _scan(self):
        if not os.path.exists(self.s1_path):
            return

        for fname in sorted(os.listdir(self.s1_path)):
            if fname.endswith(".zip") and fname.startswith("S1A_"):
                p = os.path.join(self.s1_path, fname)
                try:
                    self._parse_manifest(p, fname)
                except Exception:
                    pass

    def _parse_manifest(self, zip_p: str, name: str):
        parts = name.split("_")
        ts = parts[4] if len(parts) > 4 else "unknown"
        date_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}" if len(ts) >= 8 else "2024-07"

        poly = None
        corners = []
        with zipfile.ZipFile(zip_p, "r") as z:
            for n in z.namelist():
                if n.endswith("map-overlay.kml"):
                    content = z.read(n).decode("utf-8", errors="replace")
                    root = ET.fromstring(content)
                    for elem in root.iter():
                        if "coordinates" in elem.tag and elem.text:
                            raw = [pt.strip().split(",") for pt in elem.text.strip().split(" ") if pt.strip()]
                            pts = [(float(pt[0]), float(pt[1])) for pt in raw if len(pt) >= 2]
                            if len(pts) >= 4:
                                corners = pts[:4]
                                poly = Polygon(pts)
                            break
                    break

        if poly and len(corners) == 4:
            self.scenes.append({
                "filename": name,
                "zip_path": zip_p,
                "date": date_str,
                "acq_time": ts,
                "polygon": poly,
                "corners": corners,
                "bounds": poly.bounds,
            })

    def extract_flood_polygons(self, scene_idx: int = 0, grid_sz: int = 512) -> list[Polygon]:
        if scene_idx >= len(self.scenes):
            return []

        sc = self.scenes[scene_idx]
        zip_p = sc["zip_path"]

        vv_name = None
        with zipfile.ZipFile(zip_p, "r") as z:
            for n in z.namelist():
                if "measurement" in n and "vv" in n and n.endswith(".tiff"):
                    vv_name = n
                    break

        if not vv_name:
            return []

        vsi_path = f"/vsizip/{zip_p}/{vv_name}"
        try:
            with rasterio.open(vsi_path) as ds:
                step_y = max(1, ds.height // grid_sz)
                step_x = max(1, ds.width // grid_sz)
                raw = ds.read(1, step=(step_y, step_x)).astype(np.float32)
        except Exception:
            return []

        valid_mask = raw > 0
        if not np.any(valid_mask):
            return []

        filt = ndimage.median_filter(raw, size=3)
        vals = filt[valid_mask]
        thresh = float(np.percentile(vals, 18))

        water_bin = (filt < thresh) & valid_mask
        water_bin = ndimage.binary_opening(water_bin, structure=np.ones((2, 2)))
        water_bin = ndimage.binary_closing(water_bin, structure=np.ones((2, 2)))

        corners = sc["corners"]
        p00, p10, p11, p01 = [np.array(c) for c in corners]

        H, W = water_bin.shape
        labeled, num_features = ndimage.label(water_bin)

        extracted = []
        for feat_id in range(1, num_features + 1):
            comp = (labeled == feat_id)
            area_px = int(np.sum(comp))
            if area_px < 6:
                continue

            ys, xs = np.where(comp)
            y_min, y_max = int(ys.min()), int(ys.max())
            x_min, x_max = int(xs.min()), int(xs.max())

            def px_to_geo(col, row):
                u = col / float(W)
                v = row / float(H)
                top = (1.0 - u) * p00 + u * p10
                bot = (1.0 - u) * p01 + u * p11
                geo = (1.0 - v) * top + v * bot
                return float(geo[0]), float(geo[1])

            pts = [
                px_to_geo(x_min, y_min),
                px_to_geo(x_max, y_min),
                px_to_geo(x_max, y_max),
                px_to_geo(x_min, y_max),
                px_to_geo(x_min, y_min),
            ]
            poly = Polygon(pts)
            lat_c = poly.centroid.y
            if 25.9 <= lat_c <= 27.2:
                extracted.append(poly)

        return extracted

    def build_geojson(self, out_path: str = GEOJSON_OUT):
        all_polys = []
        for idx in range(len(self.scenes)):
            polys = self.extract_flood_polygons(idx)
            all_polys.extend(polys)

        feats = []
        for idx, poly in enumerate(all_polys):
            feat = {
                "type": "Feature",
                "id": f"flood_poly_{idx:04d}",
                "geometry": mapping(poly),
                "properties": {
                    "source": "Sentinel-1 C-band SAR GRD",
                    "event": "Assam Monsoons 2024",
                    "hazard_type": "FLOOD_WATER_SUBMERGENCE",
                    "area_km2": round(poly.area * (111.0 ** 2), 3),
                    "confidence": 0.92,
                },
            }
            feats.append(feat)

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump({"type": "FeatureCollection", "features": feats}, f, indent=2)

        self.polys = all_polys
        if all_polys:
            self._union = unary_union(all_polys)

    def _init_polygons(self):
        if os.path.exists(GEOJSON_OUT):
            try:
                with open(GEOJSON_OUT, "r") as f:
                    data = json.load(f)
                self.polys = [shape(ft["geometry"]) for ft in data.get("features", [])]
                if self.polys:
                    self._union = unary_union(self.polys)
            except Exception:
                pass
        elif self.scenes:
            self.build_geojson()

    def is_flooded(self, lat: float, lon: float, buf_deg: float = 0.0005) -> bool:
        if not self.polys:
            return False
        pt = Point(lon, lat)
        if buf_deg > 0:
            pt = pt.buffer(buf_deg)
        if self._union is not None:
            return bool(self._union.intersects(pt))
        return any(poly.intersects(pt) for poly in self.polys)
