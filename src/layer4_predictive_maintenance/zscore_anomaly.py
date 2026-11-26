"""Z-score rolling threshold anomaly detection — baseline for benchmark comparison."""
import pandas as pd
import numpy as np
from sklearn.metrics import precision_score, recall_score, confusion_matrix
from pathlib import Path
from src.layer4_predictive_maintenance.isolation_forest_anomaly import load_data, FEATURE_COLS

Z_THRESHOLD = 3.0


def detect_zscore_anomalies(threshold=Z_THRESHOLD):
    """
    Single-variable Z-score: flags anomaly if ANY feature exceeds threshold std devs.
    This is the baseline — misses multi-sensor combined fault signatures.
    """
    df = load_data()
    X = df[FEATURE_COLS]
    y_true = df["Machine failure"]

    z_scores = (X - X.mean()) / X.std()
    y_pred = (np.abs(z_scores) > threshold).any(axis=1).astype(int)

    precision = precision_score(y_true, y_pred)
    recall = recall_score(y_true, y_pred)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    fpr = fp / (fp + tn)

    print(f"Z-score (threshold={threshold}) — Precision: {precision:.3f} | Recall: {recall:.3f} | FPR: {fpr:.3f}")
    return {"precision": precision, "recall": recall, "fpr": fpr}


if __name__ == "__main__":
    detect_zscore_anomalies()