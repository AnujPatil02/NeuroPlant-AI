"""Quality KPIs per production line per shift."""


def compute_quality_kpis(total_units: int, good_units: int, scrapped_units: int, reworked_units: int):
    if total_units <= 0:
        return {"error": "total_units must be > 0"}

    return {
        "first_pass_yield": round(good_units / total_units, 4),
        "scrap_rate": round(scrapped_units / total_units, 4),
        "rework_pct": round(reworked_units / total_units, 4),
        "total_units": total_units,
    }


def defect_rate_by_type(defect_records: list[dict]):
    """defect_records: list of dicts with key 'defect_type'. Returns count per type, sorted desc."""
    counts = {}
    for r in defect_records:
        dt = r["defect_type"]
        counts[dt] = counts.get(dt, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


if __name__ == "__main__":
    kpis = compute_quality_kpis(total_units=850, good_units=800, scrapped_units=30, reworked_units=20)
    print(kpis)

    defects = [
        {"defect_type": "dimensional_variance"}, {"defect_type": "dimensional_variance"},
        {"defect_type": "surface_finish"}, {"defect_type": "dimensional_variance"},
    ]
    print(defect_rate_by_type(defects))