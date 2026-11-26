"""
SHAP explainability for XGBoost RUL model.
Generates per-machine feature importance explanation.
"""
import shap
import pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from src.layer4_predictive_maintenance.xgboost_rul import (
    load_cmapss, add_rul_target, engineer_features, get_feature_cols
)

MODEL_PATH = Path("outputs/models/xgboost_rul.pkl")
SCALER_PATH = Path("outputs/models/xgboost_scaler.pkl")


def explain_predictions(n_samples=200):
    """Run SHAP on n_samples from test set — show summary plot."""
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)

    train_df, _, _ = load_cmapss("FD001")
    train_df = add_rul_target(train_df)
    train_df = engineer_features(train_df)
    feature_cols = get_feature_cols(train_df)

    X_sample = train_df[feature_cols].sample(n_samples, random_state=42)
    X_scaled = scaler.transform(X_sample)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_scaled)

    print("\nTop 10 features driving RUL prediction:")
    mean_shap = pd.Series(
        np.abs(shap_values).mean(axis=0),
        index=feature_cols
    ).sort_values(ascending=False)
    print(mean_shap.head(10).to_string())

    # Summary plot
    shap.summary_plot(shap_values, X_scaled, feature_names=feature_cols, max_display=15, show=False)
    plt.tight_layout()
    plt.savefig("outputs/models/shap_summary.png", dpi=150)
    print("SHAP summary plot saved → outputs/models/shap_summary.png")


def explain_single_machine(sensor_dict: dict, feature_cols: list):
    """Returns top 3 SHAP drivers for a single machine reading."""
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)

    df = pd.DataFrame([sensor_dict])
    df_scaled = scaler.transform(df[feature_cols])

    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(df_scaled)[0]

    drivers = pd.Series(np.abs(shap_vals), index=feature_cols).sort_values(ascending=False)
    return drivers.head(3).to_dict()


if __name__ == "__main__":
    explain_predictions()