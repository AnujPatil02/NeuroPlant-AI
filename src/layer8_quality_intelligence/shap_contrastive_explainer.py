"""
Generates contrastive SHAP explanations for flagged quality faults —
e.g. 'Machine 7 dimensional variance fault — primary contributor: spindle RPM
deviation 8% above nominal (SHAP weight 0.61), secondary: coolant temp +4C (0.29)'
"""
import shap
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


def generate_contrastive_explanation(
    fault_record: dict,
    normal_baseline_records: list[dict],
    feature_cols: list[str],
    machine_id: str,
    fault_type: str,
):
    """
    Trains a quick IsolationForest-based explainer using normal baseline data,
    then uses SHAP KernelExplainer to attribute the fault to specific features.
    """
    X_baseline = np.array([[r[f] for f in feature_cols] for r in normal_baseline_records])
    X_fault = np.array([[fault_record[f] for f in feature_cols]])

    scaler = StandardScaler()
    X_baseline_scaled = scaler.fit_transform(X_baseline)
    X_fault_scaled = scaler.transform(X_fault)

    model = IsolationForest(contamination=0.1, random_state=42)
    model.fit(X_baseline_scaled)

    # Use decision_function as the "score" SHAP explains
    explainer = shap.KernelExplainer(model.decision_function, X_baseline_scaled[:20])
    shap_values = explainer.shap_values(X_fault_scaled, nsamples=100)[0]

    contributions = sorted(
        zip(feature_cols, shap_values, X_fault[0], X_baseline.mean(axis=0)),
        key=lambda x: abs(x[1]), reverse=True
    )

    narrative_parts = []
    labels = ["primary", "secondary", "tertiary"]
    for i, (feature, shap_val, actual_val, baseline_val) in enumerate(contributions[:2]):
        pct_dev = ((actual_val - baseline_val) / baseline_val * 100) if baseline_val != 0 else 0
        narrative_parts.append(
            f"{labels[i]} contributor: {feature} deviation of {abs(pct_dev):.1f}% "
            f"{'above' if pct_dev > 0 else 'below'} nominal (SHAP weight {abs(shap_val):.2f})"
        )

    narrative = f"Machine {machine_id} {fault_type} fault — " + ", ".join(narrative_parts) + "."

    return {
        "narrative": narrative,
        "contributions": [
            {"feature": f, "shap_weight": round(abs(v), 3), "pct_deviation": round(((a - b) / b * 100) if b != 0 else 0, 1)}
            for f, v, a, b in contributions
        ],
    }


if __name__ == "__main__":
    baseline_records = [
        {"spindle_rpm": 3200, "coolant_temp_c": 45, "feed_rate": 120}
        for _ in range(30)
    ]
    fault_record = {"spindle_rpm": 3456, "coolant_temp_c": 49, "feed_rate": 121}

    result = generate_contrastive_explanation(
        fault_record, baseline_records,
        feature_cols=["spindle_rpm", "coolant_temp_c", "feed_rate"],
        machine_id="M07", fault_type="dimensional variance",
    )
    print(result["narrative"])