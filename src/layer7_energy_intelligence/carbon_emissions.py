"""Converts energy consumption to CO2 equivalent for sustainability reporting."""

GRID_EMISSION_FACTOR_KG_CO2_PER_KWH = 0.82  # India grid average (CEA baseline)
COMPRESSED_AIR_ENERGY_INTENSITY_KWH_PER_1000L = 0.15


def electricity_to_co2(kwh: float, emission_factor: float = GRID_EMISSION_FACTOR_KG_CO2_PER_KWH) -> float:
    return round(kwh * emission_factor, 3)


def compressed_air_to_co2(litres: float, emission_factor: float = GRID_EMISSION_FACTOR_KG_CO2_PER_KWH) -> float:
    kwh_equivalent = (litres / 1000) * COMPRESSED_AIR_ENERGY_INTENSITY_KWH_PER_1000L
    return round(kwh_equivalent * emission_factor, 3)


def compute_batch_carbon_footprint(
    electricity_kwh: float,
    compressed_air_litres: float,
    units_produced: int,
):
    """Total CO2 per production batch and per unit."""
    elec_co2 = electricity_to_co2(electricity_kwh)
    air_co2 = compressed_air_to_co2(compressed_air_litres)
    total_co2 = elec_co2 + air_co2
    co2_per_unit = round(total_co2 / units_produced, 4) if units_produced > 0 else 0

    return {
        "electricity_co2_kg": elec_co2,
        "compressed_air_co2_kg": air_co2,
        "total_co2_kg": round(total_co2, 3),
        "co2_per_unit_kg": co2_per_unit,
        "units_produced": units_produced,
    }


if __name__ == "__main__":
    result = compute_batch_carbon_footprint(
        electricity_kwh=450,
        compressed_air_litres=12000,
        units_produced=850,
    )
    print(result)