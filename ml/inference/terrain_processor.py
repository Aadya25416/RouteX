import os
import math
import numpy as np
import rasterio
from rasterio.windows import Window

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEM_DIR = os.path.join(ROOT_DIR, "data", "satellite", "raw_dem")

WEST_DEM = os.path.join(DEM_DIR, "dem_west_ner.tif")
EAST_DEM = os.path.join(DEM_DIR, "dem_east_ner.tif")


class TerrainProcessor:
    def __init__(self, west_dem=WEST_DEM, east_dem=EAST_DEM):
        self.west_dem = west_dem
        self.east_dem = east_dem
        self.src_w = None
        self.src_e = None
        self._init_rasters()

    def _init_rasters(self):
        if os.path.exists(self.west_dem):
            self.src_w = rasterio.open(self.west_dem)
        if os.path.exists(self.east_dem):
            self.src_e = rasterio.open(self.east_dem)

    def close(self):
        if self.src_w:
            self.src_w.close()
            self.src_w = None
        if self.src_e:
            self.src_e.close()
            self.src_e = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _get_src(self, lat: float, lon: float):
        if self.src_w:
            b = self.src_w.bounds
            if b.left <= lon <= b.right and b.bottom <= lat <= b.top:
                return self.src_w
        if self.src_e:
            b = self.src_e.bounds
            if b.left <= lon <= b.right and b.bottom <= lat <= b.top:
                return self.src_e
        return None

    def get_terrain_features(self, lat: float, lon: float) -> dict:
        src = self._get_src(lat, lon)
        if src is None:
            return {"elevation": 0.0, "slope_deg": 0.0, "aspect_deg": 0.0, "tri": 0.0, "valid": False}

        try:
            r, c = src.index(lon, lat)
        except Exception:
            return {"elevation": 0.0, "slope_deg": 0.0, "aspect_deg": 0.0, "tri": 0.0, "valid": False}

        if r < 1 or r >= src.height - 1 or c < 1 or c >= src.width - 1:
            try:
                v = list(src.sample([(lon, lat)]))[0][0]
                elev = float(v) if v > -32000 else 0.0
                return {"elevation": elev, "slope_deg": 0.0, "aspect_deg": 0.0, "tri": 0.0, "valid": True}
            except Exception:
                return {"elevation": 0.0, "slope_deg": 0.0, "aspect_deg": 0.0, "tri": 0.0, "valid": False}

        win = Window(c - 1, r - 1, 3, 3)
        grid = src.read(1, window=win).astype(np.float32)

        nodata = src.nodata if src.nodata is not None else -32768
        grid[grid <= nodata] = np.nan
        elev = float(grid[1, 1])
        if np.isnan(elev):
            return {"elevation": 0.0, "slope_deg": 0.0, "aspect_deg": 0.0, "tri": 0.0, "valid": False}

        grid[np.isnan(grid)] = elev

        rx, ry = src.res
        dx = rx * 111320.0 * math.cos(math.radians(lat))
        dy = ry * 111320.0

        dz_dx = ((grid[0, 2] + 2 * grid[1, 2] + grid[2, 2]) -
                 (grid[0, 0] + 2 * grid[1, 0] + grid[2, 0])) / (8.0 * dx)

        dz_dy = ((grid[2, 0] + 2 * grid[2, 1] + grid[2, 2]) -
                 (grid[0, 0] + 2 * grid[0, 1] + grid[0, 2])) / (8.0 * dy)

        hypot = math.sqrt(dz_dx**2 + dz_dy**2)
        slope_deg = math.degrees(math.atan(hypot))

        if dz_dx != 0:
            aspect_deg = math.degrees(math.atan2(dz_dy, -dz_dx))
            if aspect_deg < 0:
                aspect_deg += 360.0
        else:
            aspect_deg = 90.0 if dz_dy > 0 else 270.0

        tri = float(np.mean(np.abs(grid - elev)))

        return {
            "elevation": round(elev, 1),
            "slope_deg": round(slope_deg, 2),
            "aspect_deg": round(aspect_deg, 1),
            "tri": round(tri, 2),
            "valid": True
        }

    def batch_get_terrain(self, points: list[tuple[float, float]]) -> list[dict]:
        return [self.get_terrain_features(lat, lon) for lat, lon in points]
