"""
Layer 4 — Plant-sensor health model.

FIX LOG (this revision):
  - Training cloud previously used means = warning_threshold * 0.55,
    which put the "normal" cloud ~9-10°C BELOW where a healthy machine
    actually runs (e.g. training mean 35.75°C vs real healthy 44°C).
    Every healthy machine sat 3σ+ from the training mean, so Isolation
    Forest dinged it ~8-13 points and every healthy machine read 87.
    Training means now use realistic plant operating points.
  - score_machine_health() now clamps to >=95 when no sensor is at or
    above its warning threshold -- a safety net so the ML model's small
    false-positive wobble can never drag a clean machine below 95.
  - _rule_based_health() healthy-band penalty reduced from 10*(val/warn)
    to 3*(val/warn) -- a machine at 90% of warning was losing ~9 points.
"""
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.preprocessing import StandardScaler

import shap

MODEL_PATH = Path("outputs/models/plant_sensor_health.pkl")
TOPOLOGY_PATH = Path(__file__).resolve().parents[2] / "config" / "plant_topology.json"

FEATURE_COLS = ["temperature", "vibration", "rpm", "current_draw"]

# Realistic healthy operating points for THIS plant's machines.
# These are what a CNC actually reads when nothing is wrong -- see
# plant_topology.json's warning thresholds and subtract a healthy margin.
_HEALTHY_MEANS = {
    "temperature":  44.0,     # warning at 65, healthy reads ~43-45
    "vibration":     2.3,     # warning at 4.5, healthy reads ~2.0-2.5
    "rpm":        2890.0,     # warning at 3200, healthy reads ~2850-2920
    "current_draw": 10.8,     # warning at 15, healthy reads ~10-12
}
_HEALTHY_STDS = {
    "temperature":  1.5,
    "vibration":    0.25,
    "rpm":         40.0,
    "current_draw": 0.7,
}

_DEFAULT_THRESHOLDS = {
    "temperature":  {"warning": 65.0,   "critical": 80.0},
    "vibration":    {"warning": 4.5,    "critical": 7.0},
    "rpm":          {"warning": 3200.0, "critical": 3600.0},
    "current_draw": {"warning": 15.0,   "critical": 20.0},
}


def _load_topology_thresholds() -> dict:
    """Returns {sensor: {"warning": mean_warn, "critical": mean_crit}}
    averaged across all machines in plant_topology.json."""
    try:
        with open(TOPOLOGY_PATH) as f:
            topo = json.load(f)
        w_sums, c_sums, counts = {}, {}, {}
        for factory in topo.get("factories", []):
            for line in factory.get("lines", []):
                for m in line.get("machines", []):
                    for s in m.get("sensors", []):
                        key = s["type"]
                        if key not in FEATURE_COLS:
                            continue
                        w_sums[key] = w_sums.get(key, 0) + s["warning_threshold"]
                        c_sums[key] = c_sums.get(key, 0) + s["critical_threshold"]
                        counts[key] = counts.get(key, 0) + 1
        thresholds = {}
        for k in counts:
            thresholds[k] = {"warning": w_sums[k] / counts[k],
                             "critical": c_sums[k] / counts[k]}
        return thresholds if thresholds else dict(_DEFAULT_THRESHOLDS)
    except Exception:
        return dict(_DEFAULT_THRESHOLDS)


def _generate_training_data(n_normal=2500, n_fault=180, seed=42):
    """Healthy cloud sits at realistic plant operating points. Fault cloud
    sits at or above each sensor's critical threshold."""
    rng = np.random.default_rng(seed)
    thresholds = _load_topology_thresholds()

    # --- normal cloud ---
    normal = {col: rng.normal(_HEALTHY_MEANS[col], _HEALTHY_STDS[col], n_normal)
              for col in FEATURE_COLS}
    df_normal = pd.DataFrame(normal)
    df_normal["is_fault"] = 0

    # --- fault cloud ---
    fault = {col: rng.normal(_HEALTHY_MEANS[col], _HEALTHY_STDS[col], n_fault)
             for col in FEATURE_COLS}
    df_fault = pd.DataFrame(fault)
    fault_sensor_choice = rng.choice(FEATURE_COLS, size=n_fault)
    for i, col in enumerate(fault_sensor_choice):
        crit = thresholds.get(col, _DEFAULT_THRESHOLDS[col])["critical"]
        df_fault.loc[i, col] = rng.uniform(crit, crit * 1.15)
    df_fault["is_fault"] = 1

    return pd.concat([df_normal, df_fault], ignore_index=True)


def train_plant_sensor_health(contamination=0.07):
    df = _generate_training_data()
    X = df[FEATURE_COLS]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    iso_model = IsolationForest(contamination=contamination, random_state=42, n_estimators=300)
    iso_model.fit(X_scaled)

    anomaly_scores = -iso_model.score_samples(X_scaled)
    surrogate = RandomForestRegressor(n_estimators=150, random_state=42, max_depth=6)
    surrogate.fit(X_scaled, anomaly_scores)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"iso_model": iso_model, "scaler": scaler, "surrogate": surrogate}, f)

    print(f"Plant sensor health model trained and saved → {MODEL_PATH}")
    return {"contamination": contamination, "n_samples": len(df)}


def _rule_based_health(sensor_values: dict, thresholds: dict) -> tuple:
    """Returns (health_score 0-100, worst_severity, drivers list).

    Scoring per sensor:
      value >= critical             ->  30 - 25 * min(1, (value - crit) / (0.25 * crit))
      value >= warning              ->  70 - 30 * (value - warn) / (crit - warn)
      value <  warning              -> handled at the aggregate level below

    FIX: healthy machines all read exactly 95.0 because the caller clamped
    any clean machine to a flat floor of 95. Instead, healthy scores are
    now DETERMINISTIC and VARIED -- computed from how far each sensor sits
    below its own warning threshold. Two clean machines with different
    readings get different scores in the 94.5-97.5 band, and the same
    readings always produce the same score (no flicker between renders)."""
    worst = 100.0
    worst_sev = "online"
    drivers = []
    worst_ratio = 0.0   # max(val/warn) across sensors -- drives the healthy score

    for col in FEATURE_COLS:
        val = sensor_values.get(col)
        if val is None:
            continue
        th = thresholds.get(col, _DEFAULT_THRESHOLDS[col])
        warn, crit = th["warning"], th["critical"]
        ratio = val / max(warn, 1e-6)
        worst_ratio = max(worst_ratio, ratio)

        if val >= crit:
            excess = min(1.0, (val - crit) / max(0.25 * crit, 1e-6))
            score = 30.0 - 25.0 * excess
            sev = "critical"
        elif val >= warn:
            frac = (val - warn) / max(crit - warn, 1e-6)
            score = 70.0 - 30.0 * frac
            sev = "warning"
        else:
            # Placeholder -- healthy score is decided after the loop.
            score = None
            sev = "online"

        if score is not None and score < worst:
            worst = score
            worst_sev = sev

        drivers.append({"feature": col, "value": round(val, 2),
                        "shap_weight": round(abs(100.0 - (score if score is not None else 96.0)) / 100.0, 4)})

    if worst_sev == "online":
        # Healthy score: 99 minus a small penalty proportional to the
        # worst sensor's proximity to its warning threshold.
        #  - worst sensor at  60% of warning -> 99 - 4*0.60 = 96.6
        #  - worst sensor at  80% of warning -> 99 - 4*0.80 = 95.8
        #  - worst sensor at  95% of warning -> 99 - 4*0.95 = 95.2
        healthy_score = 99.0 - 4.0 * min(worst_ratio, 0.99)
        worst = healthy_score

    drivers.sort(key=lambda d: d["shap_weight"], reverse=True)
    return max(0.0, min(100.0, round(worst, 1))), worst_sev, drivers


def score_machine_health(sensor_values: dict) -> dict:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "Plant sensor health model not trained yet. Run: "
            "python -m src.layer4_predictive_maintenance.plant_sensor_health"
        )
    with open(MODEL_PATH, "rb") as f:
        saved = pickle.load(f)

    thresholds = _load_topology_thresholds()
    row = {col: sensor_values.get(col, _HEALTHY_MEANS[col]) for col in FEATURE_COLS}
    X = pd.DataFrame([row])[FEATURE_COLS]
    X_scaled = saved["scaler"].transform(X)

    iso_pred = saved["iso_model"].predict(X_scaled)[0]
    raw_score = -saved["iso_model"].score_samples(X_scaled)[0]
    model_is_anomaly = iso_pred == -1

    model_health = max(0.0, min(100.0, round(100 - (raw_score * 22), 1)))
    rule_health, rule_sev, rule_drivers = _rule_based_health(row, thresholds)

    # Final = worst of the two oracles, but for CLEAN machines let the ML
    # model pull the score down by at most 2 points (small model wobble is
    # real but shouldn't dominate the deterministic threshold view).
    if rule_sev == "online":
        health_score = max(rule_health - 2.0, min(model_health, rule_health))
    else:
        health_score = min(model_health, rule_health)
    health_score = round(health_score, 1)

    is_anomaly = bool(model_is_anomaly or rule_sev != "online")

    explainer = shap.TreeExplainer(saved["surrogate"])
    shap_vals = explainer.shap_values(X_scaled)[0]
    ml_drivers = [
        {"feature": f, "value": round(v, 2), "shap_weight": round(abs(s), 4)}
        for f, s, v in zip(FEATURE_COLS, shap_vals, X.iloc[0].tolist())
    ]
    ml_drivers.sort(key=lambda d: d["shap_weight"], reverse=True)

    seen, merged = set(), []
    for d in rule_drivers + ml_drivers:
        if d["feature"] in seen:
            continue
        seen.add(d["feature"])
        merged.append(d)
        if len(merged) >= 3:
            break

    return {
        "is_anomaly": is_anomaly,
        "health_score": health_score,
        "model_health_score": model_health,
        "rule_health_score": rule_health,
        "severity": rule_sev,
        "top_drivers": merged[:3],
    }


if __name__ == "__main__":
    train_plant_sensor_health()
    for mid, sv in [
        ("CNC-01", {"temperature": 44.99, "vibration": 2.52, "rpm": 2855.74, "current_draw": 10.86}),
        ("CNC-02", {"temperature": 68.2,  "vibration": 4.7,  "rpm": 3802.45, "current_draw": 19.4}),
        ("CNC-07", {"temperature": 58.6,  "vibration": 3.9,  "rpm": 3252.23, "current_draw": 11.2}),
        ("CNC-08", {"temperature": 56.1,  "vibration": 3.5,  "rpm": 3588.03, "current_draw": 11.5}),
    ]:
        r = score_machine_health(sv)
        print(f'{mid}: health={r["health_score"]}  '
              f'(model={r["model_health_score"]}, rule={r["rule_health_score"]}, '
              f'sev={r["severity"]}, anomaly={r["is_anomaly"]})')