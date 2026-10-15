import os
import json
import csv
import math
import random
import datetime
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import (
    roc_auc_score,
    precision_recall_fscore_support,
    classification_report,
    log_loss,
    brier_score_loss,
    f1_score,
)
import xgboost as xgb

try:
    from ml.inference.terrain_processor import TerrainProcessor
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from ml.inference.terrain_processor import TerrainProcessor

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT_DIR, "data")
LANDSLIDE_CSV = os.path.join(DATA_DIR, "risk_features", "raw", "landslides", "nasa_glc_ner.csv")
WEATHER_DIR = os.path.join(DATA_DIR, "risk_features", "raw", "weather")
PROCESSED_DIR = os.path.join(DATA_DIR, "risk_features", "processed")
MODEL_DIR = os.path.join(ROOT_DIR, "ml", "models", "xgboost")

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

WEATHER_STATIONS = {
    "guwahati": (26.116, 91.774),
    "shillong": (25.578, 91.893),
    "itanagar": (27.084, 93.605),
    "kohima": (25.675, 94.108),
    "imphal": (24.817, 93.936),
    "aizawl": (23.730, 92.717),
    "agartala": (23.831, 91.286),
    "gangtok": (27.338, 88.606),
}


def load_weather_histories():
    weather_data = {}
    for city, (clat, clon) in WEATHER_STATIONS.items():
        fp = os.path.join(WEATHER_DIR, f"{city}_weather.json")
        if not os.path.exists(fp):
            continue
        with open(fp, "r") as f:
            raw = json.load(f)
        daily = raw.get("daily", {})
        times = daily.get("time", [])
        precip = daily.get("precipitation_sum", [])
        wind = daily.get("wind_speed_10m_max", [])

        records = {}
        for i, dt in enumerate(times):
            p = precip[i] if i < len(precip) and precip[i] is not None else 0.0
            w = wind[i] if i < len(wind) and wind[i] is not None else 10.0
            p3d = sum((precip[k] for k in range(max(0, i - 2), i + 1) if precip[k] is not None), 0.0)
            p7d = sum((precip[k] for k in range(max(0, i - 6), i + 1) if precip[k] is not None), 0.0)
            records[dt] = {
                "precip": float(p),
                "precip_3d": round(float(p3d), 1),
                "precip_7d": round(float(p7d), 1),
                "wind": float(w),
            }
        weather_data[city] = {
            "coords": (clat, clon),
            "records": records,
        }
    return weather_data


def find_nearest_station(lat, lon, weather_data):
    best_dist = float("inf")
    best_city = "guwahati"
    for city, info in weather_data.items():
        clat, clon = info["coords"]
        d = math.hypot(lat - clat, lon - clon)
        if d < best_dist:
            best_dist = d
            best_city = city
    return best_city


def extract_weather_features(lat, lon, date_str, weather_data):
    city = find_nearest_station(lat, lon, weather_data)
    records = weather_data.get(city, {}).get("records", {})

    month = 7
    dt_formatted = None

    if date_str:
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%Y %I:%M:%S %p", "%Y/%m/%d"):
            try:
                dt_obj = datetime.datetime.strptime(date_str.split(" ")[0], fmt)
                month = dt_obj.month
                dt_formatted = dt_obj.strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

    if dt_formatted and dt_formatted in records:
        r = records[dt_formatted]
        return r["precip"], r["precip_3d"], r["precip_7d"], r["wind"], month

    is_monsoon = month in (5, 6, 7, 8, 9)
    if is_monsoon:
        precip = random.uniform(15.0, 95.0)
        precip_3d = precip + random.uniform(25.0, 140.0)
        precip_7d = precip_3d + random.uniform(40.0, 220.0)
        wind = random.uniform(12.0, 35.0)
    else:
        precip = random.uniform(0.0, 10.0)
        precip_3d = random.uniform(0.0, 20.0)
        precip_7d = random.uniform(0.0, 35.0)
        wind = random.uniform(5.0, 18.0)

    return round(precip, 1), round(precip_3d, 1), round(precip_7d, 1), round(wind, 1), month


def build_dataset():
    weather_data = load_weather_histories()
    tp = TerrainProcessor()
    samples = []

    with open(LANDSLIDE_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except (ValueError, KeyError):
                continue

            t_info = tp.get_terrain_features(lat, lon)
            if not t_info["valid"] or t_info["elevation"] <= 0:
                continue

            p, p3d, p7d, wind, month = extract_weather_features(lat, lon, row.get("event_date", ""), weather_data)

            samples.append({
                "latitude": lat,
                "longitude": lon,
                "elevation": t_info["elevation"],
                "slope_deg": t_info["slope_deg"],
                "aspect_deg": t_info["aspect_deg"],
                "tri": t_info["tri"],
                "precip": p,
                "precip_3d": p3d,
                "precip_7d": p7d,
                "wind": wind,
                "month": month,
                "is_monsoon": 1 if month in (5, 6, 7, 8, 9) else 0,
                "disrupted": 1
            })

    pos_count = len(samples)
    neg_count = 0
    target_negs = int(pos_count * 1.2)

    while neg_count < target_negs:
        lat = random.uniform(22.0, 28.5)
        lon = random.uniform(89.5, 96.5)

        t_info = tp.get_terrain_features(lat, lon)
        if not t_info["valid"]:
            continue

        month = random.randint(1, 12)
        dummy_date = f"2023-{month:02d}-15"
        p, p3d, p7d, wind, _ = extract_weather_features(lat, lon, dummy_date, weather_data)

        samples.append({
            "latitude": lat,
            "longitude": lon,
            "elevation": t_info["elevation"],
            "slope_deg": t_info["slope_deg"],
            "aspect_deg": t_info["aspect_deg"],
            "tri": t_info["tri"],
            "precip": p,
            "precip_3d": p3d,
            "precip_7d": p7d,
            "wind": wind,
            "month": month,
            "is_monsoon": 1 if month in (5, 6, 7, 8, 9) else 0,
            "disrupted": 0
        })
        neg_count += 1

    tp.close()
    df = pd.DataFrame(samples)
    out_csv = os.path.join(PROCESSED_DIR, "ner_landslide_features.csv")
    df.to_csv(out_csv, index=False)
    return df


def train_model(df):
    feature_cols = [
        "elevation",
        "slope_deg",
        "aspect_deg",
        "tri",
        "precip",
        "precip_3d",
        "precip_7d",
        "wind",
        "month",
        "is_monsoon",
    ]

    x = df[feature_cols]
    y = df["disrupted"]

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_losses, cv_briers, cv_f1s, cv_aucs = [], [], [], []

    for tr_idx, va_idx in skf.split(x, y):
        x_tr, x_va = x.iloc[tr_idx], x.iloc[va_idx]
        y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]
        clf_cv = xgb.XGBClassifier(
            n_estimators=180,
            max_depth=4,
            learning_rate=0.06,
            subsample=0.95,
            colsample_bytree=0.85,
            reg_alpha=0.05,
            reg_lambda=0.8,
            scale_pos_weight=len(y_tr[y_tr == 0]) / len(y_tr[y_tr == 1]),
            eval_metric="logloss",
            device="cpu",
            n_jobs=4,
            random_state=42,
        )
        clf_cv.fit(x_tr, y_tr)
        p_cv = clf_cv.predict_proba(x_va)[:, 1]
        p_clip = np.clip(p_cv, 1e-15, 1 - 1e-15)
        cv_losses.append(log_loss(y_va, p_clip))
        cv_briers.append(brier_score_loss(y_va, p_cv))
        cv_f1s.append(f1_score(y_va, (p_cv >= 0.5).astype(int)))
        cv_aucs.append(roc_auc_score(y_va, p_cv))

    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.20, random_state=42, stratify=y)

    clf = xgb.XGBClassifier(
        n_estimators=180,
        max_depth=4,
        learning_rate=0.06,
        subsample=0.95,
        colsample_bytree=0.85,
        reg_alpha=0.05,
        reg_lambda=0.8,
        scale_pos_weight=len(y_train[y_train == 0]) / len(y_train[y_train == 1]),
        eval_metric="logloss",
        device="cpu",
        n_jobs=4,
        random_state=42,
    )

    clf.fit(x_train, y_train, eval_set=[(x_train, y_train), (x_test, y_test)], verbose=False)

    preds_prob = clf.predict_proba(x_test)[:, 1]
    preds_binary = (preds_prob >= 0.5).astype(int)

    auc = roc_auc_score(y_test, preds_prob)
    prec, rec, f1, _ = precision_recall_fscore_support(y_test, preds_binary, average="binary")

    importances = clf.feature_importances_
    feat_imp = sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)

    model_path = os.path.join(MODEL_DIR, "landslide_risk_xgboost.json")
    clf.save_model(model_path)

    metadata = {
        "model_name": "xgboost_ner_landslide_risk",
        "model_version": "1.1.0",
        "hyperparameters": {
            "max_depth": 4,
            "learning_rate": 0.06,
            "subsample": 0.95,
            "colsample_bytree": 0.85,
            "reg_alpha": 0.05,
            "reg_lambda": 0.8,
            "n_estimators": 180,
        },
        "cv_5fold_metrics": {
            "mean_logloss": round(float(np.mean(cv_losses)), 4),
            "std_logloss": round(float(np.std(cv_losses)), 4),
            "mean_brier_score": round(float(np.mean(cv_briers)), 4),
            "std_brier_score": round(float(np.std(cv_briers)), 4),
            "mean_f1": round(float(np.mean(cv_f1s)), 4),
            "std_f1": round(float(np.std(cv_f1s)), 4),
            "mean_auc_roc": round(float(np.mean(cv_aucs)), 4),
            "std_auc_roc": round(float(np.std(cv_aucs)), 4),
        },
        "test_metrics": {
            "auc_roc": round(float(auc), 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1_score": round(float(f1), 4),
        },
        "features": feature_cols,
        "feature_importances": {feat: round(float(imp), 4) for feat, imp in feat_imp},
        "trained_samples": len(x_train),
        "test_samples": len(x_test),
    }

    meta_path = os.path.join(MODEL_DIR, "model_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)


if __name__ == "__main__":
    data = build_dataset()
    train_model(data)
