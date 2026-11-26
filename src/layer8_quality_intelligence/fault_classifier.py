"""
Isolation Forest on multi-variable quality sensor streams (dimension, surface finish,
weight). Flags anomalous quality events, classified by machine/shift/product/fault type.
"""
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

FAULT_TYPE_LIBRARY = [
    "dimensional_variance", "surface_finish_defect", "weight_deviation", "tool_wear_pattern"
]


def classify_quality_faults(quality_records: list[dict], contamination: float = 0.05):
    """
    quality_records: list of dicts with keys:
        machine_id, shift, product_sku, dimension_mm, surface_finish_ra, weight_g
    Returns flagged records with fault classification.
    """
    features = ["dimension_mm", "surface_finish_ra", "weight_g"]
    X = np.array([[r[f] for f in features] for r in quality_records])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(contamination=contamination, random_state=42)
    preds = model.fit_predict(X_scaled)

    flagged = []
    for i, r in enumerate(quality_records):
        if preds[i] == -1:
            # crude fault-type assignment based on which feature deviates most
            z_scores = np.abs(X_scaled[i])
            dominant_feature = features[np.argmax(z_scores)]
            fault_type_map = {
                "dimension_mm": "dimensional_variance",
                "surface_finish_ra": "surface_finish_defect",
                "weight_g": "weight_deviation",
            }
            flagged.append({
                "machine_id": r["machine_id"],
                "shift": r["shift"],
                "product_sku": r["product_sku"],
                "fault_type": fault_type_map[dominant_feature],
                "dominant_feature": dominant_feature,
            })
    return flagged


if __name__ == "__main__":
    records = [
        {"machine_id": "M01", "shift": "morning", "product_sku": "SKU-118", "dimension_mm": 25.02, "surface_finish_ra": 1.2, "weight_g": 450},
        {"machine_id": "M01", "shift": "morning", "product_sku": "SKU-118", "dimension_mm": 25.01, "surface_finish_ra": 1.1, "weight_g": 448},
        {"machine_id": "M07", "shift": "evening", "product_sku": "SKU-118", "dimension_mm": 27.4, "surface_finish_ra": 1.3, "weight_g": 452},  # anomalous
    ]
    print(classify_quality_faults(records))