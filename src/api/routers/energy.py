# energy.py
"""
Layer 7 Multi-Utility Energy Intelligence API — electricity, compressed air,
water/steam monitoring, energy anomaly detection, carbon footprint.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.layer7_energy_intelligence.electricity_monitor import compute_machine_energy, track_peak_demand
from src.layer7_energy_intelligence.compressed_air_monitor import establish_baseline, detect_leak
from src.layer7_energy_intelligence.water_steam_monitor import track_water_consumption, compute_steam_efficiency
from src.layer7_energy_intelligence.energy_anomaly_detector import detect_energy_anomalies
from src.layer7_energy_intelligence.carbon_emissions import compute_batch_carbon_footprint

router = APIRouter(prefix="/energy", tags=["energy"])


class ElectricityRequest(BaseModel):
    machine_id: str
    current_readings: list[float]
    interval_minutes: float = 1.0


class PeakDemandRequest(BaseModel):
    kw_readings_15min: list[float]
    contract_limit_kw: float


class LeakBaselineRequest(BaseModel):
    historical_flow_readings: list[float]


class LeakDetectRequest(BaseModel):
    current_flow_readings: list[float]
    baseline: dict
    deviation_threshold_pct: float = 15.0
    sustained_minutes: int = 20
    reading_interval_minutes: float = 1.0


class WaterRequest(BaseModel):
    litres_used: float
    cycles_completed: int
    benchmark_litres_per_cycle: float


class SteamRequest(BaseModel):
    steam_flow_kg_per_hour: float
    steam_temperature_c: float
    process_step: str
    benchmark_kj_per_kg_product: float
    product_kg_processed: float


class EnergyRecord(BaseModel):
    machine_id: str
    hourly_kwh: float
    hourly_units_produced: float


class CarbonRequest(BaseModel):
    electricity_kwh: float
    compressed_air_litres: float
    units_produced: int


@router.post("/electricity/machine")
async def machine_energy(req: ElectricityRequest):
    """kWh consumption for a machine (e.g. CNC-07) from current-draw readings."""
    return compute_machine_energy(req.machine_id, req.current_readings, req.interval_minutes)


@router.post("/electricity/peak-demand")
async def peak_demand(req: PeakDemandRequest):
    """15-min demand window vs utility contract limit."""
    return track_peak_demand(req.kw_readings_15min, req.contract_limit_kw)


@router.post("/compressed-air/baseline")
async def air_baseline(req: LeakBaselineRequest):
    """Establishes 2-week flow baseline for a machine/zone's pneumatic circuit."""
    return establish_baseline(req.historical_flow_readings)


@router.post("/compressed-air/leak-check")
async def air_leak_check(req: LeakDetectRequest):
    """Flags a compressed-air leak if flow deviates >threshold for sustained_minutes."""
    return detect_leak(
        req.current_flow_readings, req.baseline,
        req.deviation_threshold_pct, req.sustained_minutes, req.reading_interval_minutes,
    )


@router.post("/water")
async def water_consumption(req: WaterRequest):
    """Water consumption per cycle vs benchmark (e.g. ZONE_TREATMENT cooling circuit)."""
    return track_water_consumption(req.litres_used, req.cycles_completed, req.benchmark_litres_per_cycle)


@router.post("/steam")
async def steam_efficiency(req: SteamRequest):
    """Steam energy content per kg product vs benchmark (e.g. heat treatment step)."""
    return compute_steam_efficiency(
        req.steam_flow_kg_per_hour, req.steam_temperature_c, req.process_step,
        req.benchmark_kj_per_kg_product, req.product_kg_processed,
    )


@router.post("/anomalies")
async def energy_anomalies(records: list[EnergyRecord]):
    """Isolation Forest on energy-per-unit across machines — flags abnormal consumers."""
    if not records:
        raise HTTPException(status_code=400, detail="At least one energy record required")
    return {"results": detect_energy_anomalies([r.model_dump() for r in records])}


@router.post("/carbon-footprint")
async def carbon_footprint(req: CarbonRequest):
    """Total CO2 per batch and per unit from electricity + compressed air."""
    return compute_batch_carbon_footprint(req.electricity_kwh, req.compressed_air_litres, req.units_produced)