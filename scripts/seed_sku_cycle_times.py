"""
Seeds the sku_cycle_times table from plant_topology.json's product_skus block.
plant_topology.json is the single source of truth for SKU->cycle-time mapping;
this script keeps the database in sync with it. Run once after init_db(),
and re-run any time plant_topology.json's product_skus list changes.
"""
import json
from pathlib import Path
from src.layer3_oee.models import SessionLocal, SKUCycleTime

TOPOLOGY_PATH = Path(__file__).parent.parent / "config" / "plant_topology.json"


def seed_sku_cycle_times():
    with open(TOPOLOGY_PATH) as f:
        topology = json.load(f)

    session = SessionLocal()
    added, updated = 0, 0

    for sku in topology.get("product_skus", []):
        existing = session.query(SKUCycleTime).filter(
            SKUCycleTime.product_sku == sku["sku"]
        ).first()

        if existing:
            existing.ideal_cycle_time_seconds = sku["ideal_cycle_time_sec"]
            updated += 1
        else:
            session.add(SKUCycleTime(
                product_sku=sku["sku"],
                ideal_cycle_time_seconds=sku["ideal_cycle_time_sec"],
            ))
            added += 1

    session.commit()
    session.close()
    print(f"SKU cycle times seeded: {added} added, {updated} updated")


if __name__ == "__main__":
    seed_sku_cycle_times()