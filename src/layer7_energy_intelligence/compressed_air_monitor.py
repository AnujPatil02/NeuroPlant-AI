"""
Compressed air leak detection — baseline established from first 2 weeks,
flags deviations > 15% for > 20 min as leak alerts.
"""
import numpy as np


def establish_baseline(historical_flow_readings: list[float]) -> dict:
    """Call this once with 2 weeks of data per machine/operating mode."""
    return {
        "mean_flow_lpm": round(np.mean(historical_flow_readings), 2),
        "std_flow_lpm": round(np.std(historical_flow_readings), 2),
    }


def detect_leak(
    current_flow_readings: list[float],
    baseline: dict,
    deviation_threshold_pct: float = 15.0,
    sustained_minutes: int = 20,
    reading_interval_minutes: float = 1.0,
):
    """
    current_flow_readings: recent flow readings (litres/min), most recent last.
    Flags leak if deviation exceeds threshold for sustained_minutes continuously.
    """
    baseline_mean = baseline["mean_flow_lpm"]
    required_consecutive = int(sustained_minutes / reading_interval_minutes)

    deviations = [(r - baseline_mean) / baseline_mean * 100 for r in current_flow_readings]
    exceeding = [d > deviation_threshold_pct for d in deviations]

    # Check for sustained consecutive exceedance
    max_consecutive = 0
    consecutive = 0
    for e in exceeding:
        consecutive = consecutive + 1 if e else 0
        max_consecutive = max(max_consecutive, consecutive)

    leak_detected = max_consecutive >= required_consecutive
    estimated_leak_rate_lpm = round(np.mean(current_flow_readings) - baseline_mean, 2) if leak_detected else 0

    # Convert leak rate to energy waste estimate (typical: 7 kW per 100 cfm ~ 0.24 kW per lpm)
    estimated_energy_waste_kwh_per_hour = round(estimated_leak_rate_lpm * 0.24, 2) if leak_detected else 0

    return {
        "leak_detected": leak_detected,
        "sustained_minutes_exceeded": max_consecutive * reading_interval_minutes,
        "estimated_leak_rate_lpm": estimated_leak_rate_lpm,
        "estimated_energy_waste_kwh_per_hour": estimated_energy_waste_kwh_per_hour,
    }


if __name__ == "__main__":
    baseline = establish_baseline([100, 102, 98, 101, 99, 103, 100])
    print("Baseline:", baseline)

    # Simulate a leak — flow rises 25% above baseline for 25 consecutive minutes
    current_readings = [125] * 25
    result = detect_leak(current_readings, baseline)
    print("Leak detection:", result)