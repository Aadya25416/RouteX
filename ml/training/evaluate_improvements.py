"""
5-Fold Stratified Cross-Validation Benchmark Suite for RouteX Risk Model.
Compares Baseline XGBoost vs Enhanced Regularized + Scaled + Calibrated Model.
"""

import os
import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import RobustScaler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    log_loss,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
)
import xgboost as xgb

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "risk_features", "processed", "ner_landslide_features.csv")


def engineer_features(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = df_raw.copy()

    # Aspect sin/cos continuous representation
    aspect_rad = np.radians(df["aspect_deg"])
    df["aspect_sin"] = np.sin(aspect_rad)
    df["aspect_cos"] = np.cos(aspect_rad)

    # Physical Interaction: Slope * log(1 + Antecedent Rain)
    df["slope_x_rain3d"] = df["slope_deg"] * np.log1p(df["precip_3d"])
    df["slope_x_rain7d"] = df["slope_deg"] * np.log1p(df["precip_7d"])

    # Terrain instability: Slope * TRI
    df["slope_x_tri"] = df["slope_deg"] * df["tri"]

    # Antecedent saturation ratio
    df["saturation_ratio"] = df["precip_3d"] / (df["precip_7d"] + 1.0)

    # Non-linear log rainfall
    df["log_precip"] = np.log1p(df["precip"])
    df["log_precip_3d"] = np.log1p(df["precip_3d"])
    df["log_precip_7d"] = np.log1p(df["precip_7d"])

    # High hazard threshold (>20 deg)
    df["is_steep_slope"] = (df["slope_deg"] >= 20.0).astype(int)

    feature_cols = [
        "elevation",
        "slope_deg",
        "tri",
        "aspect_sin",
        "aspect_cos",
        "slope_x_rain3d",
        "slope_x_rain7d",
        "slope_x_tri",
        "saturation_ratio",
        "log_precip",
        "log_precip_3d",
        "log_precip_7d",
        "wind",
        "month",
        "is_monsoon",
        "is_steep_slope",
    ]
    return df, feature_cols


def run_benchmark():
    print("=" * 75, flush=True)
    print("  RouteX 5-Fold Stratified Cross-Validation Benchmark", flush=True)
    print("=" * 75, flush=True)

    df_raw = pd.read_csv(DATA_PATH)
    y = df_raw["disrupted"].values

    baseline_cols = [
        "elevation", "slope_deg", "aspect_deg", "tri",
        "precip", "precip_3d", "precip_7d", "wind", "month", "is_monsoon"
    ]
    X_baseline = df_raw[baseline_cols].values

    df_enhanced, enhanced_cols = engineer_features(df_raw)
    X_enhanced = df_enhanced[enhanced_cols].values

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    base_metrics = {"auc": [], "pr_auc": [], "logloss": [], "brier": [], "f1": [], "prec": [], "rec": []}
    enh_metrics = {"auc": [], "pr_auc": [], "logloss": [], "brier": [], "f1": [], "prec": [], "rec": []}

    for fold, (train_idx, val_idx) in enumerate(skf.split(X_baseline, y), 1):
        y_tr, y_va = y[train_idx], y[val_idx]

        # 1. Baseline Model
        base_xgb = xgb.XGBClassifier(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.85,
            colsample_bytree=0.85,
            scale_pos_weight=len(y_tr[y_tr == 0]) / len(y_tr[y_tr == 1]),
            eval_metric="logloss",
            device="cpu",
            n_jobs=4,
            random_state=42,
        )
        base_xgb.fit(X_baseline[train_idx], y_tr)
        p_base = base_xgb.predict_proba(X_baseline[val_idx])[:, 1]
        p_base_clip = np.clip(p_base, 1e-15, 1 - 1e-15)
        pred_base = (p_base >= 0.5).astype(int)

        base_metrics["auc"].append(roc_auc_score(y_va, p_base))
        base_metrics["pr_auc"].append(average_precision_score(y_va, p_base))
        base_metrics["logloss"].append(log_loss(y_va, p_base_clip))
        base_metrics["brier"].append(brier_score_loss(y_va, p_base))
        base_metrics["f1"].append(f1_score(y_va, pred_base))
        base_metrics["prec"].append(precision_score(y_va, pred_base))
        base_metrics["rec"].append(recall_score(y_va, pred_base))

        # 2. Enhanced Model: RobustScaler + Regularized XGBoost + Probability Calibration
        scaler = RobustScaler()
        X_tr_s = scaler.fit_transform(X_enhanced[train_idx])
        X_va_s = scaler.transform(X_enhanced[val_idx])

        enh_xgb = xgb.XGBClassifier(
            n_estimators=120,
            max_depth=4,
            learning_rate=0.03,
            subsample=0.80,
            colsample_bytree=0.80,
            reg_alpha=0.5,
            reg_lambda=2.0,
            min_child_weight=3,
            gamma=0.1,
            scale_pos_weight=len(y_tr[y_tr == 0]) / len(y_tr[y_tr == 1]),
            eval_metric="logloss",
            device="cpu",
            n_jobs=4,
            random_state=42,
        )

        cal_model = CalibratedClassifierCV(estimator=enh_xgb, method="sigmoid", cv=3)
        cal_model.fit(X_tr_s, y_tr)
        p_enh = cal_model.predict_proba(X_va_s)[:, 1]
        p_enh_clip = np.clip(p_enh, 1e-15, 1 - 1e-15)
        pred_enh = (p_enh >= 0.5).astype(int)

        enh_metrics["auc"].append(roc_auc_score(y_va, p_enh))
        enh_metrics["pr_auc"].append(average_precision_score(y_va, p_enh))
        enh_metrics["logloss"].append(log_loss(y_va, p_enh_clip))
        enh_metrics["brier"].append(brier_score_loss(y_va, p_enh))
        enh_metrics["f1"].append(f1_score(y_va, pred_enh))
        enh_metrics["prec"].append(precision_score(y_va, pred_enh))
        enh_metrics["rec"].append(recall_score(y_va, pred_enh))

        print(f"Fold {fold}/5: Base LogLoss={base_metrics['logloss'][-1]:.4f}, Enh LogLoss={enh_metrics['logloss'][-1]:.4f} | Base Brier={base_metrics['brier'][-1]:.4f}, Enh Brier={enh_metrics['brier'][-1]:.4f}", flush=True)

    print("\n" + "=" * 80, flush=True)
    print("  5-FOLD STRATIFIED CROSS-VALIDATION SUMMARY (Mean ± Std)", flush=True)
    print("=" * 80, flush=True)
    print(f"{'Metric':<25} | {'Baseline Model':<22} | {'Enhanced Model':<22} | {'Improvement'}", flush=True)
    print("-" * 80, flush=True)

    comparisons = [
        ("logloss", "Log Loss (Cross-Entropy)", True),
        ("brier", "Brier Score (Prob Error)", True),
        ("auc", "ROC-AUC Score", False),
        ("pr_auc", "PR-AUC (Avg Precision)", False),
        ("f1", "F1-Score", False),
        ("prec", "Precision", False),
        ("rec", "Recall", False),
    ]

    for key, label, lower_better in comparisons:
        b_m = np.mean(base_metrics[key])
        b_s = np.std(base_metrics[key])
        e_m = np.mean(enh_metrics[key])
        e_s = np.std(enh_metrics[key])

        if lower_better:
            pct = ((b_m - e_m) / b_m) * 100
            winner = f"Enhanced ({pct:+.1f}%)" if e_m < b_m else f"Baseline ({pct:+.1f}%)"
        else:
            diff = e_m - b_m
            winner = f"Enhanced ({diff:+.4f})" if e_m > b_m else f"Baseline ({diff:+.4f})"

        print(f"{label:<25} | {b_m:.4f} ± {b_s:.4f}        | {e_m:.4f} ± {e_s:.4f}        | {winner}", flush=True)

    brier_better = np.mean(enh_metrics["brier"]) < np.mean(base_metrics["brier"])
    logloss_better = np.mean(enh_metrics["logloss"]) < np.mean(base_metrics["logloss"])
    is_better = brier_better and logloss_better

    print("=" * 80, flush=True)
    print(f"VERDICT: {'ENHANCED MODEL IS SUPERIOR' if is_better else 'BASELINE MODEL IS SUPERIOR'}", flush=True)
    print("=" * 80, flush=True)
    return is_better, enhanced_cols


if __name__ == "__main__":
    run_benchmark()
