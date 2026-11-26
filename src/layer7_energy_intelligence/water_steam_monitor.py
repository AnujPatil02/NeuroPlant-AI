"""
Water consumption per cycle (cooling circuits) and steam energy content
(heat treatment/cleaning stations) tracked against product benchmarks.
"""

STEAM_ENERGY_KJ_PER_KG = 2257  # latent heat of vaporization, standard steam tables


def track_water_consumption(litres_used: float, cycles_completed: int, benchmark_litres_per_cycle: float):
    """Flags cooling system inefficiency or leak if consumption exceeds benchmark."""
    actual_per_cycle = round(litres_used / cycles_completed, 2) if cycles_completed > 0 else 0
    pct_over_benchmark = ((actual_per_cycle - benchmark_litres_per_cycle) / benchmark_litres_per_cycle * 100) \
        if benchmark_litres_per_cycle > 0 else 0

    return {
        "actual_litres_per_cycle": actual_per_cycle,
        "benchmark_litres_per_cycle": benchmark_litres_per_cycle,
        "pct_over_benchmark": round(pct_over_benchmark, 1),
        "flagged": pct_over_benchmark > 15.0,
        "diagnosis": "Possible cooling system leak or inefficiency" if pct_over_benchmark > 15.0 else "Normal",
    }


def compute_steam_efficiency(
    steam_flow_kg_per_hour: float,
    steam_temperature_c: float,
    process_step: str,
    benchmark_kj_per_kg_product: float,
    product_kg_processed: float,
):
    """Energy content per kg steam vs benchmark per process step."""
    energy_content_kj = steam_flow_kg_per_hour * STEAM_ENERGY_KJ_PER_KG
    actual_kj_per_kg_product = round(energy_content_kj / product_kg_processed, 2) if product_kg_processed > 0 else 0
    pct_over_benchmark = ((actual_kj_per_kg_product - benchmark_kj_per_kg_product) / benchmark_kj_per_kg_product * 100) \
        if benchmark_kj_per_kg_product > 0 else 0

    return {
        "process_step": process_step,
        "steam_flow_kg_per_hour": steam_flow_kg_per_hour,
        "energy_content_kj": round(energy_content_kj, 1),
        "actual_kj_per_kg_product": actual_kj_per_kg_product,
        "benchmark_kj_per_kg_product": benchmark_kj_per_kg_product,
        "pct_over_benchmark": round(pct_over_benchmark, 1),
        "efficiency_flag": "Inefficient — investigate insulation/trap losses" if pct_over_benchmark > 10.0 else "Efficient",
    }


if __name__ == "__main__":
    water_result = track_water_consumption(litres_used=850, cycles_completed=100, benchmark_litres_per_cycle=7.0)
    print("Water:", water_result)

    steam_result = compute_steam_efficiency(
        steam_flow_kg_per_hour=45,
        steam_temperature_c=180,
        process_step="heat_treatment",
        benchmark_kj_per_kg_product=850,
        product_kg_processed=110,
    )
    print("Steam:", steam_result)