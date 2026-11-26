"""Runs XGBoost + LSTM RUL benchmark and prints comparison table with business reasoning."""
from src.layer4_predictive_maintenance import xgboost_rul, lstm_rul


def run_benchmark():
    print("=" * 60)
    print("RUL MODEL BENCHMARK — XGBoost vs LSTM (CMAPSS FD001)")
    print("=" * 60)

    _, _, _, xgb_rmse, xgb_mae = xgboost_rul.train()
    lstm_rmse, lstm_mae = lstm_rul.train()

    print("\n" + "=" * 60)
    print(f"{'Model':<15}{'RMSE':<10}{'MAE':<10}{'Interpretability':<15}")
    print("-" * 60)
    print(f"{'XGBoost':<15}{xgb_rmse:<10.2f}{xgb_mae:<10.2f}{'High (SHAP)':<15}")
    print(f"{'LSTM':<15}{lstm_rmse:<10.2f}{lstm_mae:<10.2f}{'Low':<15}")
    print("=" * 60)
    print("\nNote: TFT (PyTorch Forecasting) evaluated but excluded — broken")
    print("lightning_cloud dependency chain in pytorch-forecasting 1.2.0 causes")
    print("unresolvable ImportError. XGBoost recommended as PRIMARY model for")
    print("maintenance scheduling due to SHAP interpretability.")


if __name__ == "__main__":
    run_benchmark()