"""
MLflow model registry — logs training runs, tracks metrics across model versions,
promotes best model to Production stage for API serving.
"""
import mlflow
import mlflow.xgboost
import mlflow.keras
from src.config.settings import settings

mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
EXPERIMENT_NAME = "neuroplant-rul-prediction"


def log_xgboost_run(model, params: dict, metrics: dict, run_name="xgboost_rul"):
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        mlflow.xgboost.log_model(model, "model", registered_model_name="xgboost_rul_model")
        print(f"Logged run: {run_name} | RMSE: {metrics.get('rmse')} | MAE: {metrics.get('mae')}")


def log_lstm_run(model, params: dict, metrics: dict, run_name="lstm_rul"):
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        mlflow.keras.log_model(model, "model", registered_model_name="lstm_rul_model")
        print(f"Logged run: {run_name} | RMSE: {metrics.get('rmse')} | MAE: {metrics.get('mae')}")


def promote_best_model(model_name: str, version: int, stage: str = "Production"):
    """Promotes a specific model version to Production/Staging in the registry."""
    client = mlflow.MlflowClient()
    client.transition_model_version_stage(name=model_name, version=version, stage=stage)
    print(f"Model {model_name} v{version} promoted to {stage}")


def get_production_model(model_name: str):
    """Loads the current Production-stage model for serving."""
    model_uri = f"models:/{model_name}/Production"
    return mlflow.pyfunc.load_model(model_uri)


def compare_runs(experiment_name: str = EXPERIMENT_NAME):
    """Prints all runs sorted by RMSE — helps decide which to promote."""
    client = mlflow.MlflowClient()
    experiment = client.get_experiment_by_name(experiment_name)
    if not experiment:
        print("No experiment found yet — run training first.")
        return

    runs = client.search_runs(experiment.experiment_id, order_by=["metrics.rmse ASC"])
    print(f"\n{'Run Name':<20}{'RMSE':<10}{'MAE':<10}")
    print("-" * 40)
    for run in runs:
        print(f"{run.data.tags.get('mlflow.runName', 'unnamed'):<20}"
              f"{run.data.metrics.get('rmse', 'N/A'):<10}"
              f"{run.data.metrics.get('mae', 'N/A'):<10}")


if __name__ == "__main__":
    compare_runs()