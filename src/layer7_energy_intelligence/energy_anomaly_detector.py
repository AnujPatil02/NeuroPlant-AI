"""Isolation Forest on per-machine hourly energy consumption — flags abnormal usage relative to production rate."""
import numpy as np
from sklearn.ensemble import IsolationForest


def detect_energy_anomalies(energy_production_records: list[dict], contamination: float = 0.05):
    """
    energy_production_records: list of dicts with keys:
        machine_id, hourly_kwh, hourly_units_produced
    Flags machines consuming abnormally relative to production rate (energy per unit).
    """
    energy_per_unit = [
        r["hourly_kwh"] / r["hourly_units_produced"] if r["hourly_units_produced"] > 0 else 0
        for r in energy_production_records
    ]
    X = np.array(energy_per_unit).reshape(-1, 1)

    model = IsolationForest(contamination=contamination, random_state=42)
    preds = model.fit_predict(X)

    results = []
    for i, r in enumerate(energy_production_records):
        results.append({
            "machine_id": r["machine_id"],
            "energy_per_unit_kwh": round(energy_per_unit[i], 3),
            "anomaly": preds[i] == -1,
        })
    return results


if __name__ == "__main__":
    records = [
        {"machine_id": "M01", "hourly_kwh": 12, "hourly_units_produced": 50},
        {"machine_id": "M02", "hourly_kwh": 13, "hourly_units_produced": 52},
        {"machine_id": "M03", "hourly_kwh": 35, "hourly_units_produced": 48},  # abnormal — high energy, normal output
        {"machine_id": "M04", "hourly_kwh": 11, "hourly_units_produced": 49},
    ]
    results = detect_energy_anomalies(records)
    for r in results:
        flag = "ANOMALY" if r["anomaly"] else "normal"
        print(f"{r['machine_id']}: {r['energy_per_unit_kwh']} kWh/unit — {flag}")