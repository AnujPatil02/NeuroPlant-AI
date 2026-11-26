"""
Production simulation engine — models output over 24-72h given a proposed
schedule change (shift hours, line rebalancing, maintenance window).
Uses current machine health (RUL) and OEE history to project throughput.
"""
import numpy as np


def simulate_production(
    line_id: str,
    current_oee: float,
    ideal_units_per_hour: float,
    horizon_hours: int = 24,
    scheduled_downtime_hours: float = 0.0,
    machine_health_factor: float = 1.0,  # 1.0 = healthy, <1.0 = degraded (from RUL)
):
    """
    Projects total units, estimated OEE, and flags where machine health
    limits throughput over the simulation horizon.
    """
    available_hours = max(horizon_hours - scheduled_downtime_hours, 0)

    # Effective OEE degrades if machine health factor drops (early fault signs)
    effective_oee = current_oee * machine_health_factor
    projected_units = round(available_hours * ideal_units_per_hour * effective_oee)

    constraint_flagged = machine_health_factor < 0.85
    constraint_msg = (
        f"Machine health factor {machine_health_factor:.2f} limits throughput — "
        f"consider maintenance before this window" if constraint_flagged else None
    )

    return {
        "line_id": line_id,
        "horizon_hours": horizon_hours,
        "scheduled_downtime_hours": scheduled_downtime_hours,
        "projected_total_units": projected_units,
        "estimated_oee": round(effective_oee, 4),
        "constraint_flagged": constraint_flagged,
        "constraint_message": constraint_msg,
    }


def test_schedule_change(
    line_id: str,
    baseline_oee: float,
    ideal_units_per_hour: float,
    proposed_shift_hours: float,
    proposed_maintenance_hours: float,
    machine_health_factor: float = 1.0,
):
    """
    Compares baseline (no change) vs proposed schedule change.
    Used to test shift start times, staffing, maintenance windows before deployment.
    """
    baseline = simulate_production(
        line_id, baseline_oee, ideal_units_per_hour,
        horizon_hours=proposed_shift_hours, scheduled_downtime_hours=0.0,
        machine_health_factor=machine_health_factor
    )
    proposed = simulate_production(
        line_id, baseline_oee, ideal_units_per_hour,
        horizon_hours=proposed_shift_hours, scheduled_downtime_hours=proposed_maintenance_hours,
        machine_health_factor=machine_health_factor
    )

    unit_diff = proposed["projected_total_units"] - baseline["projected_total_units"]
    return {
        "baseline": baseline,
        "proposed": proposed,
        "unit_impact": unit_diff,
        "recommendation": (
            "Schedule conflict — deploy maintenance in a lower-demand window"
            if abs(unit_diff) > (0.1 * baseline["projected_total_units"])
            else "Safe to deploy — minimal production impact"
        )
    }


if __name__ == "__main__":
    result = test_schedule_change(
        line_id="LINE01",
        baseline_oee=0.78,
        ideal_units_per_hour=50,
        proposed_shift_hours=24,
        proposed_maintenance_hours=4,
        machine_health_factor=0.90,
    )
    print(f"Baseline units: {result['baseline']['projected_total_units']}")
    print(f"Proposed units: {result['proposed']['projected_total_units']}")
    print(f"Unit impact: {result['unit_impact']}")
    print(f"Recommendation: {result['recommendation']}")