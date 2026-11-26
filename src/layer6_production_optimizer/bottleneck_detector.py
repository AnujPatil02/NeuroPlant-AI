"""
Detects bottleneck stations: actual cycle time > design cycle time by threshold.
Also detects queue buildup (buffer occupancy) and material shortage signals.
"""


def detect_bottlenecks(stations: list[dict], threshold_pct: float = 15.0):
    """
    stations: list of dicts with keys:
        station_id, design_cycle_time_sec, actual_cycle_time_sec
    Returns stations flagged as bottlenecks with % over design.
    """
    bottlenecks = []
    for s in stations:
        pct_over = ((s["actual_cycle_time_sec"] - s["design_cycle_time_sec"])
                    / s["design_cycle_time_sec"] * 100)
        if pct_over > threshold_pct:
            bottlenecks.append({
                "station_id": s["station_id"],
                "design_cycle_time_sec": s["design_cycle_time_sec"],
                "actual_cycle_time_sec": s["actual_cycle_time_sec"],
                "pct_over_design": round(pct_over, 1),
            })
    return sorted(bottlenecks, key=lambda x: x["pct_over_design"], reverse=True)


def detect_queue_buildup(buffer_readings: list[dict], occupancy_threshold: float = 85.0, min_consecutive: int = 2):
    """
    buffer_readings: list of dicts with keys:
        buffer_id, occupancy_pct_history (list of last N readings)
    Flags buffers exceeding threshold for >= min_consecutive readings.
    """
    alerts = []
    for b in buffer_readings:
        history = b["occupancy_pct_history"]
        consecutive = 0
        max_consecutive = 0
        for val in history:
            if val > occupancy_threshold:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0
        if max_consecutive >= min_consecutive:
            alerts.append({
                "buffer_id": b["buffer_id"],
                "current_occupancy": history[-1],
                "consecutive_high_readings": max_consecutive,
                "signal": "upstream rate mismatch or downstream blockage",
            })
    return alerts


def detect_material_shortage(production_count: int, expected_count: int, machine_running: bool, threshold_pct: float = 10.0):
    """
    Flags material shortage when production is below expected DESPITE machine running
    (i.e. performance loss not explained by downtime).
    """
    if not machine_running:
        return {"flagged": False, "reason": "machine not running — not a material issue"}

    shortfall_pct = ((expected_count - production_count) / expected_count * 100) if expected_count > 0 else 0
    flagged = shortfall_pct > threshold_pct

    return {
        "flagged": flagged,
        "shortfall_pct": round(shortfall_pct, 1),
        "reason": "check material feed — production below expected while machine running" if flagged else "normal",
    }


if __name__ == "__main__":
    stations = [
        {"station_id": "ST01", "design_cycle_time_sec": 30, "actual_cycle_time_sec": 32},
        {"station_id": "ST02", "design_cycle_time_sec": 25, "actual_cycle_time_sec": 38},
        {"station_id": "ST03", "design_cycle_time_sec": 40, "actual_cycle_time_sec": 41},
    ]
    print("Bottlenecks:", detect_bottlenecks(stations))

    buffers = [{"buffer_id": "BUF01", "occupancy_pct_history": [70, 88, 91, 93, 60]}]
    print("Queue buildup:", detect_queue_buildup(buffers))

    print("Material shortage:", detect_material_shortage(production_count=380, expected_count=450, machine_running=True))