"""
Temporal Fusion Transformer RUL prediction — multi-horizon forecast with attention.
Highest accuracy on long degradation sequences, highest computational cost.
"""
import pandas as pd
import numpy as np
import torch
from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer
from pytorch_forecasting.data import GroupNormalizer
from pytorch_forecasting.metrics import RMSE, MAE
from lightning.pytorch import Trainer as pl_Trainer
from lightning.pytorch.callbacks import EarlyStopping
from pathlib import Path
from src.layer4_predictive_maintenance.xgboost_rul import load_cmapss, add_rul_target, SENSOR_COLS

MODEL_DIR = Path("outputs/models/tft_rul")
MAX_ENCODER_LENGTH = 30
MAX_PREDICTION_LENGTH = 10


def prepare_data():
    train_df, _, _ = load_cmapss("FD001")
    train_df = add_rul_target(train_df)
    train_df["unit"] = train_df["unit"].astype(str)
    train_df["time_idx"] = train_df.groupby("unit").cumcount()
    return train_df


def train():
    print("Loading CMAPSS FD001...")
    df = prepare_data()

    training_cutoff = df["time_idx"].max() - MAX_PREDICTION_LENGTH

    training = TimeSeriesDataSet(
        df[df.time_idx <= training_cutoff],
        time_idx="time_idx",
        target="RUL",
        group_ids=["unit"],
        max_encoder_length=MAX_ENCODER_LENGTH,
        max_prediction_length=MAX_PREDICTION_LENGTH,
        time_varying_unknown_reals=SENSOR_COLS + ["RUL"],
        target_normalizer=GroupNormalizer(groups=["unit"]),
        add_relative_time_idx=True,
        add_target_scales=True,
    )
    validation = TimeSeriesDataSet.from_dataset(training, df, predict=True, stop_randomization=True)

    train_loader = training.to_dataloader(train=True, batch_size=64, num_workers=0)
    val_loader = validation.to_dataloader(train=False, batch_size=64, num_workers=0)

    tft = TemporalFusionTransformer.from_dataset(
        training,
        learning_rate=0.03,
        hidden_size=16,
        attention_head_size=2,
        dropout=0.1,
        loss=RMSE(),
        log_interval=10,
        reduce_on_plateau_patience=4,
    )

    early_stop = EarlyStopping(monitor="val_loss", patience=3, mode="min")
    trainer = pl_Trainer(
    max_epochs=15,
    accelerator="cpu",
    gradient_clip_val=0.1,
    callbacks=[early_stop],
    enable_progress_bar=True,
)

    print("Training TFT...")
    trainer.fit(tft, train_dataloaders=train_loader, val_dataloaders=val_loader)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_checkpoint(MODEL_DIR / "tft_model.ckpt")
    print(f"Model saved → {MODEL_DIR / 'tft_model.ckpt'}")

    # Evaluate
    predictions = tft.predict(val_loader, mode="prediction", return_y=True)
    preds_flat = predictions.output.numpy().flatten()
    actuals_flat = predictions.y[0].numpy().flatten()
    rmse = np.sqrt(np.mean((preds_flat - actuals_flat) ** 2))
    mae = np.mean(np.abs(preds_flat - actuals_flat))
    print(f"\nTFT Results — RMSE: {rmse:.2f} | MAE: {mae:.2f}")

    return rmse, mae


if __name__ == "__main__":
    train()