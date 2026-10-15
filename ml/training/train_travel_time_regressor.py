import os
import sys
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

OUT_DIR = os.path.join(ROOT_DIR, "ml", "models", "xgboost")
DATA_DIR = os.path.join(ROOT_DIR, "data", "risk_features", "processed")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)


def build_telemetry_dataset(n: int = 3000) -> pd.DataFrame:
    rng = np.random.RandomState(42)

    r_classes = rng.choice([0, 1, 2, 3, 4], size=n, p=[0.10, 0.25, 0.30, 0.20, 0.15])
    speeds = np.array([75.0, 60.0, 45.0, 35.0, 25.0])[r_classes]

    elev = rng.uniform(50.0, 3800.0, size=n)
    slopes = np.clip(rng.exponential(scale=8.0, size=n), 0.0, 42.0)
    tri = slopes * rng.uniform(0.15, 0.45, size=n)

    monsoon = rng.choice([0, 1], size=n, p=[0.45, 0.55])
    rain = np.where(monsoon == 1, rng.exponential(scale=28.0, size=n), rng.exponential(scale=3.0, size=n))
    rain = np.clip(rain, 0.0, 160.0)

    p_slope = np.clip(slopes / 30.0, 0.0, 0.50)
    p_rain = np.clip(np.log1p(rain) / 6.0, 0.0, 0.40)
    p_alt = np.where(elev > 2500.0, (elev - 2500.0) / 4000.0, 0.0)
    p_joint = np.where((slopes > 15.0) & (rain > 40.0), 0.15, 0.0)

    noise = rng.normal(0.0, 0.03, size=n)
    deg = np.clip(1.0 - (p_slope + p_rain + p_alt + p_joint) + noise, 0.20, 1.00)

    v_eff = speeds * deg
    delay_mult = 1.0 / deg

    df = pd.DataFrame({
        "road_class": r_classes,
        "base_speed_kmh": speeds,
        "elevation_m": np.round(elev, 1),
        "slope_deg": np.round(slopes, 2),
        "tri": np.round(tri, 2),
        "rain_mm": np.round(rain, 1),
        "is_monsoon": monsoon,
        "degradation_factor": np.round(deg, 3),
        "effective_speed_kmh": np.round(v_eff, 1),
        "delay_multiplier": np.round(delay_mult, 2),
    })

    out_csv = os.path.join(DATA_DIR, "mountain_speed_telemetry.csv")
    df.to_csv(out_csv, index=False)
    return df


def train_regressor(df: pd.DataFrame):
    cols = [
        "road_class",
        "base_speed_kmh",
        "elevation_m",
        "slope_deg",
        "tri",
        "rain_mm",
        "is_monsoon",
    ]

    x = df[cols]
    y = df["degradation_factor"]

    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.20, random_state=42)

    model = xgb.XGBRegressor(
        n_estimators=160,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.90,
        colsample_bytree=0.85,
        reg_alpha=0.05,
        reg_lambda=1.0,
        eval_metric="rmse",
        device="cpu",
        n_jobs=4,
        random_state=42,
    )

    model.fit(x_train, y_train, eval_set=[(x_test, y_test)], verbose=False)

    preds = model.predict(x_test)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    model_path = os.path.join(OUT_DIR, "travel_delay_xgboost.json")
    model.save_model(model_path)

    meta_path = os.path.join(OUT_DIR, "travel_delay_metadata.json")
    with open(meta_path, "w") as f:
        json.dump({
            "model_name": "xgboost_mountain_speed_degradation",
            "model_version": "1.0.0",
            "metrics": {
                "rmse": round(float(rmse), 4),
                "mae": round(float(mae), 4),
                "r2_score": round(float(r2), 4),
            },
            "features": cols,
            "trained_samples": len(x_train),
            "test_samples": len(x_test),
        }, f, indent=2)


if __name__ == "__main__":
    data = build_telemetry_dataset(3000)
    train_regressor(data)
