"""
XGBoost RUL prediction on NASA CMAPSS dataset.
Features: rolling mean, rolling std, lag features per sensor.
Target: Remaining Useful Life (cycles to failure).
"""
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.preprocessing import MinMaxScaler
import pickle
from pathlib import Path

from src.layer4_predictive_maintenance.model_registry import log_xgboost_run

DATA_PATH = Path("data/raw/cmapss")
MODEL_PATH = Path("outputs/models/xgboost_rul.pkl")
SCALER_PATH = Path("outputs/models/xgboost_scaler.pkl")

# CMAPSS column names
SENSOR_COLS = [f"s{i}" for i in range(1, 22)]
SETTING_COLS = ["setting1", "setting2", "setting3"]
ALL_COLS = ["unit", "cycle"] + SETTING_COLS + SENSOR_COLS


def load_cmapss(subset="FD001"):
    train = pd.read_csv(DATA_PATH / f"train_{subset}.txt", sep=r"\s+", header=None)
    train.columns = ALL_COLS
    test = pd.read_csv(DATA_PATH / f"test_{subset}.txt", sep=r"\s+", header=None)
    test.columns = ALL_COLS
    rul = pd.read_csv(DATA_PATH / f"RUL_{subset}.txt", sep=r"\s+", header=None, names=["RUL"])
    return train, test, rul


def add_rul_target(df):
    """Add RUL column — cycles remaining until failure per unit."""
    max_cycle = df.groupby("unit")["cycle"].max().reset_index()
    max_cycle.columns = ["unit", "max_cycle"]
    df = df.merge(max_cycle, on="unit")
    df["RUL"] = df["max_cycle"] - df["cycle"]
    # Clip RUL at 125 — piecewise linear target (standard CMAPSS practice)
    df["RUL"] = df["RUL"].clip(upper=125)
    return df.drop(columns=["max_cycle"])


def engineer_features(df, window=10):
    """Rolling mean + std + lag features per sensor per unit."""
    feature_dfs = []
    for unit_id, group in df.groupby("unit"):
        group = group.sort_values("cycle")
        for col in SENSOR_COLS:
            group[f"{col}_mean{window}"] = group[col].rolling(window, min_periods=1).mean()
            group[f"{col}_std{window}"] = group[col].rolling(window, min_periods=1).std().fillna(0)
            group[f"{col}_lag1"] = group[col].shift(1).fillna(method="bfill")
        feature_dfs.append(group)
    return pd.concat(feature_dfs, ignore_index=True)


def get_feature_cols(df):
    return [c for c in df.columns if c not in ["unit", "cycle", "RUL"] + SETTING_COLS]


def train():
    print("Loading CMAPSS FD001...")
    train_df, _, _ = load_cmapss("FD001")
    train_df = add_rul_target(train_df)
    train_df = engineer_features(train_df)
    
    feature_cols = get_feature_cols(train_df)
    X = train_df[feature_cols]
    y = train_df["RUL"]

    # Time-based split — last 20% cycles of each unit go to test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    scaler = MinMaxScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = xgb.XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )
    print("Training XGBoost...")
    model.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=50)

    preds = model.predict(X_test_s)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mae = mean_absolute_error(y_test, preds)
    print(f"\nResults — RMSE: {rmse:.2f} | MAE: {mae:.2f}")

    # Save model + scaler
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    print(f"Model saved → {MODEL_PATH}")

    log_xgboost_run(
    model,
    params={"n_estimators": 300, "max_depth": 6, "learning_rate": 0.05},
    metrics={"rmse": rmse, "mae": mae},
)
    return model, scaler, feature_cols, rmse, mae


def predict_rul(sensor_dict: dict) -> float:
    """Predict RUL for a single machine given latest sensor readings dict."""
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)
    df = pd.DataFrame([sensor_dict])
    df_scaled = scaler.transform(df)
    return float(model.predict(df_scaled)[0])


if __name__ == "__main__":
    train()