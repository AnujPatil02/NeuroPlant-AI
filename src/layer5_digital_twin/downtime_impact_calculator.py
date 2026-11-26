"""
Downtime impact calculator — computes production/revenue loss over the RUL window
if a machine fault is predicted, plus cascade effect on dependent downstream lines.
"""


def calculate_downtime_impact(
    machine_id: str,
    rul_days: float,
    units_per_hour: float,
    product_value_per_unit: float,
    downstream_dependent_lines: list[str] = None,
    cascade_factor: float = 0.5,  # fraction of downstream line output also lost
):
    """
    If machine fails at RUL, computes:
    - units lost if unplanned failure occurs (assume 8hr emergency repair)
    - revenue impact
    - cascade effect on downstream lines
    """
    emergency_repair_hours = 8.0  # standard assumption for unplanned breakdown
    units_lost = round(units_per_hour * emergency_repair_hours)
    revenue_impact = round(units_lost * product_value_per_unit, 2)

    cascade_impact = {}
    if downstream_dependent_lines:
        for line in downstream_dependent_lines:
            cascade_units_lost = round(units_lost * cascade_factor)
            cascade_impact[line] = {
                "units_lost": cascade_units_lost,
                "revenue_impact": round(cascade_units_lost * product_value_per_unit, 2),
            }

    total_revenue_impact = revenue_impact + sum(c["revenue_impact"] for c in cascade_impact.values())

    return {
        "machine_id": machine_id,
        "rul_days": rul_days,
        "direct_units_lost": units_lost,
        "direct_revenue_impact": revenue_impact,
        "cascade_impact": cascade_impact,
        "total_revenue_impact": total_revenue_impact,
        "urgency": "CRITICAL" if rul_days < 5 else "HIGH" if rul_days < 15 else "MODERATE",
    }


if __name__ == "__main__":
    result = calculate_downtime_impact(
        machine_id="M01",
        rul_days=3.5,
        units_per_hour=40,
        product_value_per_unit=25.0,
        downstream_dependent_lines=["LINE02", "LINE03"],
        cascade_factor=0.4,
    )
    print(f"Machine: {result['machine_id']} | Urgency: {result['urgency']}")
    print(f"Direct impact: {result['direct_units_lost']} units, ${result['direct_revenue_impact']}")
    for line, impact in result["cascade_impact"].items():
        print(f"  Cascade → {line}: {impact['units_lost']} units, ${impact['revenue_impact']}")
    print(f"Total revenue impact: ${result['total_revenue_impact']}")