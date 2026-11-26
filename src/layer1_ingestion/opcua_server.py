# opcua_server.py
"""
OPC-UA server — exposes all machines from plant_topology.json as node tree.
Each machine has nodes: sensor values + operating_mode + production_count + maintenance_status.
Digital Twin (Layer 5) reads these nodes for live state replication.
"""
import asyncio
import json
from pathlib import Path
from asyncua import Server

TOPOLOGY_PATH = Path(__file__).parent.parent / "config" / "plant_topology.json"


async def _add_machine_node(parent_node, idx, machine, node_map):
    """Creates the Objects/Variables for one machine under parent_node.
    Shared by both line machines (CNC-01..12) and zone machines (ASM-01)."""
    m_id = machine["machine_id"]
    machine_node = await parent_node.add_object(idx, m_id)
    node_map[m_id] = {}

    node_map[m_id]["operating_mode"] = await machine_node.add_variable(idx, "operating_mode", "Running")
    node_map[m_id]["production_count"] = await machine_node.add_variable(idx, "production_count", 0)
    node_map[m_id]["maintenance_status"] = await machine_node.add_variable(idx, "maintenance_status", "OK")

    for sensor in machine["sensors"]:
        node_map[m_id][sensor["type"]] = await machine_node.add_variable(idx, sensor["type"], 0.0)
        await node_map[m_id][sensor["type"]].set_writable()


async def run_opcua_server():
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/neuroplant/server/")
    server.set_server_name("NeuroPlant OPC-UA Server")

    uri = "http://neuroplant.ai/opcua"
    idx = await server.register_namespace(uri)

    with open(TOPOLOGY_PATH) as f:
        topology = json.load(f)

    node_map = {}

    for factory in topology["factories"]:
        fac_node = await server.nodes.objects.add_object(idx, factory["factory_id"])

        for line in factory["lines"]:
            line_node = await fac_node.add_object(idx, line["line_id"])
            for machine in line["machines"]:
                await _add_machine_node(line_node, idx, machine, node_map)

        zones_node = await fac_node.add_object(idx, "Zones")
        for zone in topology.get("zones", []):
            zone_node = await zones_node.add_object(idx, zone["zone_id"])

            if zone.get("sensors"):
                zone_as_machine = {
                    "machine_id": zone["zone_id"],
                    "sensors": zone["sensors"],
                }
                await _add_machine_node(zone_node, idx, zone_as_machine, node_map)

            for machine in zone.get("machines", []):
                await _add_machine_node(zone_node, idx, machine, node_map)

    print("OPC-UA Server running at opc.tcp://localhost:4840/neuroplant/server/")

    import random
    from src.layer1_ingestion.synthetic_sensor_generator import BASE_VALUES, generate_reading

    async with server:
        count = 0
        while True:
            count += 1
            for factory in topology["factories"]:
                for line in factory["lines"]:
                    for machine in line["machines"]:
                        m_id = machine["machine_id"]
                        for sensor in machine["sensors"]:
                            val = generate_reading(sensor["type"], BASE_VALUES[sensor["type"]])
                            await node_map[m_id][sensor["type"]].write_value(val)
                        await node_map[m_id]["production_count"].write_value(count * random.randint(1, 3))

                for zone in topology.get("zones", []):
                    zone_id = zone["zone_id"]
                    if zone.get("sensors") and zone_id in node_map:
                        for sensor in zone["sensors"]:
                            val = generate_reading(sensor["type"], BASE_VALUES[sensor["type"]])
                            await node_map[zone_id][sensor["type"]].write_value(val)
                        await node_map[zone_id]["production_count"].write_value(count * random.randint(1, 3))
                    for machine in zone.get("machines", []):
                        m_id = machine["machine_id"]
                        for sensor in machine["sensors"]:
                            val = generate_reading(sensor["type"], BASE_VALUES[sensor["type"]])
                            await node_map[m_id][sensor["type"]].write_value(val)
                        await node_map[m_id]["production_count"].write_value(count * random.randint(1, 3))

            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(run_opcua_server())