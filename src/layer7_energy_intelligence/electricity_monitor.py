"""Converts machine current draw to kWh consumption, tracks peak demand."""
from datetime import datetime


def current_to_kwh(current_amps: float, voltage: float = 415, power_factor: float = 0.85, hours: float = 1.0) -> float:
    """Standard 3-phase power formula: kW = (V x I x PF x sqrt(3)) / 1000."""
    kw = (voltage * current_amps * power_factor * 1.732) / 1000
    return round(kw * hours, 3)


def compute_machine_energy(machine_id: str, current_readings: list[float], interval_minutes: float = 1.0):
    """Sums kWh across a series of current readings taken at fixed intervals."""
    hours_per_reading = interval_minutes / 60
    total_kwh = sum(current_to_kwh(c, hours=hours_per_reading) for c in current_readings)
    return {
        "machine_id": machine_id,
        "total_kwh": round(total_kwh, 3),
        "num_readings": len(current_readings),
        "avg_kw": round(total_kwh / (len(current_readings) * hours_per_reading), 3) if current_readings else 0,
    }


def track_peak_demand(kw_readings_15min: list[float], contract_limit_kw: float):
    """15-min demand window tracking — flags approach to utility contract limit."""
    peak_kw = max(kw_readings_15min) if kw_readings_15min else 0
    pct_of_limit = (peak_kw / contract_limit_kw * 100) if contract_limit_kw > 0 else 0
    return {
        "peak_kw": peak_kw,
        "contract_limit_kw": contract_limit_kw,
        "pct_of_limit": round(pct_of_limit, 1),
        "alert": pct_of_limit > 85,
    }


if __name__ == "__main__":
    readings = [8.5, 9.1, 8.8, 12.4, 9.0]  # amps, sampled every 1 min
    result = compute_machine_energy("M01", readings)
    print(result)

    demand = track_peak_demand([45, 52, 48, 61], contract_limit_kw=65)
    print(demand)