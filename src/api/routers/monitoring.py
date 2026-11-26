"""
Layer 2 Real-Time Monitoring API — serves live sensor readings and OPC-UA
machine state so Streamlit/GenAI pull real data instead of hardcoded samples.
"""
from fastapi import APIRouter, HTTPException
from src.layer1_ingestion.synthetic_sensor_generator import get_all_readings, load_topology
from src.layer1_ingestion.opcua_client import read_all_nodes

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/readings")
async def get_readings(fault_machine_id: str | None = None):
    """All current sensor readings across every machine and zone.
    Pass fault_machine_id to simulate a degrading machine (e.g. CNC-07)."""
    return {"readings": get_all_readings(fault_machine_id)}


@router.get("/readings/{machine_id}")
async def get_machine_readings(machine_id: str, fault_machine_id: str | None = None):
    """Sensor readings for a single machine or zone (e.g. CNC-07, ZONE_TREATMENT)."""
    readings = get_all_readings(fault_machine_id)
    machine_readings = [r for r in readings if r["machine_id"] == machine_id]
    if not machine_readings:
        raise HTTPException(status_code=404, detail=f"No readings found for '{machine_id}'")
    return {"machine_id": machine_id, "readings": machine_readings}


@router.get("/topology")
async def get_topology():
    """Full plant topology — factories, lines, machines, zones, SKUs."""
    return load_topology()


@router.get("/machines")
async def list_machines():
    """Flat list of every machine_id across lines and zones — for dropdowns/selectors."""
    topology = load_topology()
    machines = []
    for factory in topology["factories"]:
        for line in factory["lines"]:
            for m in line["machines"]:
                machines.append({
                    "machine_id": m["machine_id"],
                    "machine_type": m["machine_type"],
                    "component": m.get("component"),
                    "line_id": line["line_id"],
                    "line_name": line["line_name"],
                })
    for zone in topology.get("zones", []):
        for m in zone.get("machines", []):
            machines.append({
                "machine_id": m["machine_id"],
                "machine_type": m["machine_type"],
                "component": m.get("component"),
                "line_id": zone["zone_id"],
                "line_name": zone["zone_name"],
            })
    return {"machines": machines}


@router.get("/twin-state")
async def get_twin_state():
    """Live OPC-UA node state — used by Layer 5 Digital Twin for state mirroring."""
    try:
        state = await read_all_nodes()
        return {"twin_state": state}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"OPC-UA server unreachable: {e}")