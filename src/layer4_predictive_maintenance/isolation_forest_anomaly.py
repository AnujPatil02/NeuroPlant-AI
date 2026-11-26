"""Isolation Forest anomaly detection on AI4I 2020 — multi-sensor fault detection."""
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, confusion_matrix
from pathlib import Path
import pickle

DATA_PATH = Path("data/raw/ai4i/ai4i2020.csv")
MODEL_PATH = Path("outputs/models/isolation_forest.pkl")

FEATURE_COLS = [
    "Air temperature [K]", "Process temperature [K]",
    "Rotational speed [rpm]", "Torque [Nm]", "Tool wear [min]"
]


def load_data():
    df = pd.read_csv(DATA_PATH)
    # Add interaction feature — torque*RPM captures power anomaly better
    df["power_proxy"] = df["Rotational speed [rpm]"] * df["Torque [Nm]"]
    return df

FEATURE_COLS = [
    "Air temperature [K]", "Process temperature [K]",
    "Rotational speed [rpm]", "Torque [Nm]", "Tool wear [min]",
    "power_proxy"
]


def train_isolation_forest(contamination=0.035):
    """contamination = expected fault rate; AI4I has ~3.4% actual failure rate."""
    df = load_data()
    X = df[FEATURE_COLS]
    y_true = df["Machine failure"]  # 1 = fault, 0 = normal

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Change contamination and n_estimators:
    model = IsolationForest(contamination=0.034, random_state=42, n_estimators=500, max_samples="auto")
    preds = model.fit_predict(X_scaled)  # -1 = anomaly, 1 = normal
    y_pred = np.where(preds == -1, 1, 0)  # convert to 1=fault, 0=normal

    precision = precision_score(y_true, y_pred)
    recall = recall_score(y_true, y_pred)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    fpr = fp / (fp + tn)

    print(f"Isolation Forest — Precision: {precision:.3f} | Recall: {recall:.3f} | FPR: {fpr:.3f}")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model, "scaler": scaler}, f)

    return {"precision": precision, "recall": recall, "fpr": fpr}


def predict_anomaly(sensor_values: dict) -> bool:
    with open(MODEL_PATH, "rb") as f:
        saved = pickle.load(f)
    X = pd.DataFrame([sensor_values])[FEATURE_COLS]
    X_scaled = saved["scaler"].transform(X)
    pred = saved["model"].predict(X_scaled)
    return pred[0] == -1


if __name__ == "__main__":
    train_isolation_forest()