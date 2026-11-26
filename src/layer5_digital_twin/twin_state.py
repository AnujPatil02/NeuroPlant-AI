"""
Digital Twin state store — mirrors OPC-UA machine state + adds OEE/RUL context.
Updated every 2s from OPC-UA feed (Layer 1), queryable via REST API (Layer 10).
"""
import asyncio
from datetime import datetime
from src.layer1_ingestion.opcua_client import read_all_nodes

_twin_state = {}  # in-memory cache, updated by background loop


async def refresh_twin_state():
    """Pulls latest OPC-UA state into twin cache. Call this on a loop or on-demand."""
    global _twin_state
    raw_state = await read_all_nodes()
    for machine_id, params in raw_state.items():
        _twin_state[machine_id] = {
            **params,
            "last_updated": datetime.now().isoformat(),
        }
    return _twin_state


def get_twin_state(machine_id: str | None = None):
    """Returns full twin state, or single machine if machine_id given."""
    if machine_id:
        return _twin_state.get(machine_id, {})
    return _twin_state


def enrich_with_oee_rul(machine_id: str, oee_value: float, rul_days: float):
    """Attach OEE and RUL context to a machine's twin state — called after Layer 3/4 compute."""
    if machine_id in _twin_state:
        _twin_state[machine_id]["oee_contribution"] = oee_value
        _twin_state[machine_id]["rul_days"] = rul_days


async def background_refresh_loop(interval_seconds=2):
    """Run this as a background task to keep twin state live."""
    while True:
        await refresh_twin_state()
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    asyncio.run(refresh_twin_state())
    print(get_twin_state())