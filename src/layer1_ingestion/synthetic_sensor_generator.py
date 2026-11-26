"""Generates realistic sensor values with optional fault injection.

FIX: get_all_readings() / _machine_reading() only ever accepted a single
fault_machine_id, so at most one machine in the whole plant could ever
show a warning/critical value at a time -- every other machine was always
"good". Extended to accept a LIST of fault machine ids (fault_machine_id
still works as a single string for backward compatibility with existing
callers), so multiple machines can be flagged simultaneously -- matching
what a real plant floor looks like (several machines drifting/at-risk at
once, not just one).
"""
import random
import json
from pathlib import Path

TOPOLOGY_PATH = Path(__file__).parent.parent / "config" / "plant_topology.json"


def load_topology():
    with open(TOPOLOGY_PATH) as f:
        return json.load(f)


def generate_reading(sensor_type: str, base_value: float, fault_mode: bool = False) -> float:
    """Simulates normal reading, or a drifting fault value if fault_mode=True."""
    noise = random.uniform(-0.02, 0.02) * base_value
    if fault_mode:
        drift = random.uniform(0.15, 0.35) * base_value  # abnormal spike
        return round(base_value + drift + noise, 2)
    return round(base_value + noise, 2)


# Baseline "normal" values per sensor type
BASE_VALUES = {
    "vibration": 2.5,
    "temperature": 45.0,
    "current_draw": 10.0,
    "rpm": 2800.0,
    "pressure": 4.5,
    "humidity": 50.0,
}

# FIX: a small, fixed set of machines that are ALWAYS flagged as
# drifting/at-risk in this demo/synthetic data, so the Alarm Timeline,
# Machine Health Matrix, and Live Telemetry sections consistently show
# several non-normal machines instead of exactly zero or exactly one.
# Mirrors the same machines already used as the "flagged" examples
# elsewhere in this project (CNC-02 critical, CNC-07/CNC-08 warning in
# the Digital Twin demo roster) so the story is consistent across pages.
DEFAULT_FAULT_MACHINE_IDS = {"CNC-02", "CNC-07", "CNC-08"}


def _resolve_fault_ids(fault_machine_id) -> set:
    """Normalizes the fault_machine_id argument -- accepts None, a single
    string (old call signature, kept for backward compatibility), or a
    list/set/tuple of machine ids (new)."""
    if fault_machine_id is None:
        return set(DEFAULT_FAULT_MACHINE_IDS)
    if isinstance(fault_machine_id, str):
        return {fault_machine_id}
    return set(fault_machine_id)


def _machine_reading(factory_id, line_id, machine, fault_ids: set):
    """Builds sensor readings for one machine dict. line_id may be a zone_id for zone machines."""
    is_fault = machine["machine_id"] in fault_ids
    out = []
    for sensor in machine["sensors"]:
        value = generate_reading(sensor["type"], BASE_VALUES[sensor["type"]], is_fault)
        out.append({
            "factory_id": factory_id,
            "line_id": line_id,
            "machine_id": machine["machine_id"],
            "sensor_type": sensor["type"],
            "value": value,
            "unit": sensor["unit"],
            "warning_threshold": sensor["warning_threshold"],
            "critical_threshold": sensor["critical_threshold"],
        })
    return out


def get_all_readings(fault_machine_id=None):
    """Returns list of dicts: one reading per sensor per machine, across production
    lines AND zone-level machines/sensors (e.g. process treatment, assembly).

    fault_machine_id: None (uses DEFAULT_FAULT_MACHINE_IDS so several
    machines show realistic warning/critical values), a single machine_id
    string (old behavior, flags just that one machine), or a
    list/set/tuple of machine_id strings (flags all of them)."""
    topology = load_topology()
    readings = []
    fault_ids = _resolve_fault_ids(fault_machine_id)

    for factory in topology["factories"]:
        factory_id = factory["factory_id"]

        # Production line machines (the 12 CNC machining centres)
        for line in factory["lines"]:
            for machine in line["machines"]:
                readings.extend(_machine_reading(factory_id, line["line_id"], machine, fault_ids))

        # Zone-level readings (process treatment sensors, assembly robot, etc.)
        for zone in topology.get("zones", []):
            zone_id = zone["zone_id"]

            for sensor in zone.get("sensors", []):
                is_fault = zone_id in fault_ids
                value = generate_reading(sensor["type"], BASE_VALUES[sensor["type"]], is_fault)
                readings.append({
                    "factory_id": factory_id,
                    "line_id": zone_id,
                    "machine_id": zone_id,
                    "sensor_type": sensor["type"],
                    "value": value,
                    "unit": sensor["unit"],
                    "warning_threshold": sensor["warning_threshold"],
                    "critical_threshold": sensor["critical_threshold"],
                })

            for machine in zone.get("machines", []):
                readings.extend(_machine_reading(factory_id, zone_id, machine, fault_ids))

    return readings