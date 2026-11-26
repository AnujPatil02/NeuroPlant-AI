"""
LSTM RUL prediction — sequence-to-one on 30-cycle sensor windows.
Captures temporal degradation patterns XGBoost's engineered features approximate.
"""
import numpy as np
import pandas as pd
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
import pickle
from pathlib import Path
from src.layer4_predictive_maintenance.xgboost_rul import load_cmapss, add_rul_target, SENSOR_COLS

WINDOW = 30
MODEL_PATH = Path("outputs/models/lstm_rul.keras")
SCALER_PATH = Path("outputs/models/lstm_scaler.pkl")


def build_sequences(df, window=WINDOW):
    """Build (samples, window, features) sequences per unit, padding short units."""
    X, y = [], []
    for unit_id, group in df.groupby("unit"):
        group = group.sort_values("cycle")
        data = group[SENSOR_COLS].values
        targets = group["RUL"].values
        n = len(data)
        if n < window:
            pad = np.repeat(data[0:1], window - n, axis=0)
            data = np.vstack([pad, data])
            n = window
        for i in range(window, n + 1):
            X.append(data[i - window:i])
            y.append(targets[min(i - 1, len(targets) - 1)])
    return np.array(X), np.array(y)


def build_model(n_features):
    model = keras.Sequential([
        layers.Input(shape=(WINDOW, n_features)),
        layers.LSTM(64, return_sequences=True),
        layers.Dropout(0.2),
        layers.LSTM(32),
        layers.Dropout(0.2),
        layers.Dense(16, activation="relu"),
        layers.Dense(1)
    ])
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model


def train():
    print("Loading CMAPSS FD001...")
    train_df, _, _ = load_cmapss("FD001")
    train_df = add_rul_target(train_df)

    scaler = MinMaxScaler()
    train_df[SENSOR_COLS] = scaler.fit_transform(train_df[SENSOR_COLS])

    X, y = build_sequences(train_df)
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = build_model(n_features=len(SENSOR_COLS))
    print("Training LSTM...")
    model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=20, batch_size=64, verbose=1
    )

    preds = model.predict(X_test).flatten()
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mae = mean_absolute_error(y_test, preds)
    print(f"\nLSTM Results — RMSE: {rmse:.2f} | MAE: {mae:.2f}")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    print(f"Model saved → {MODEL_PATH}")

    return rmse, mae


if __name__ == "__main__":
    train()