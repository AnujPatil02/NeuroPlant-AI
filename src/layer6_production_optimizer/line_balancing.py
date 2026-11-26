"""
Line balancing recommendation — when a bottleneck station is found, analyzes
adjacent stations for spare capacity and recommends workload redistribution.
"""


def recommend_line_balancing(stations: list[dict], bottleneck_station_id: str):
    """
    stations: list of dicts with keys: station_id, design_cycle_time_sec, actual_cycle_time_sec
    Finds adjacent stations (by list order) with spare capacity (actual < design)
    and recommends shifting workload from bottleneck to them.
    """
    idx = next((i for i, s in enumerate(stations) if s["station_id"] == bottleneck_station_id), None)
    if idx is None:
        return {"error": f"Station {bottleneck_station_id} not found"}

    bottleneck = stations[idx]
    candidates = []

    for offset in [-1, 1]:  # check immediate neighbors
        n_idx = idx + offset
        if 0 <= n_idx < len(stations):
            neighbor = stations[n_idx]
            spare_capacity = neighbor["design_cycle_time_sec"] - neighbor["actual_cycle_time_sec"]
            if spare_capacity > 0:
                candidates.append({
                    "station_id": neighbor["station_id"],
                    "spare_capacity_sec": spare_capacity,
                })

    if not candidates:
        return {
            "bottleneck": bottleneck_station_id,
            "recommendation": "No adjacent spare capacity found — consider adding shift capacity or new equipment",
        }

    best = max(candidates, key=lambda x: x["spare_capacity_sec"])
    shift_amount = min(
        best["spare_capacity_sec"],
        bottleneck["actual_cycle_time_sec"] - bottleneck["design_cycle_time_sec"],
    )

    return {
        "bottleneck": bottleneck_station_id,
        "recommended_target": best["station_id"],
        "shift_workload_sec": round(shift_amount, 1),
        "recommendation": f"Shift {round(shift_amount,1)}s of task load from {bottleneck_station_id} to {best['station_id']}",
    }


if __name__ == "__main__":
    stations = [
        {"station_id": "ST01", "design_cycle_time_sec": 30, "actual_cycle_time_sec": 25},
        {"station_id": "ST02", "design_cycle_time_sec": 25, "actual_cycle_time_sec": 38},
        {"station_id": "ST03", "design_cycle_time_sec": 40, "actual_cycle_time_sec": 35},
    ]
    result = recommend_line_balancing(stations, "ST02")
    print(result)