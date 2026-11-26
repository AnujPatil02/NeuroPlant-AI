"""
OPC-UA client — reads current machine state from OPC-UA server.
Used by Layer 5 Digital Twin to mirror live factory state.
"""
import asyncio
from asyncua import Client
from src.config.settings import settings


async def _is_leaf_machine_node(node) -> bool:
    """A machine node's children are all Variables (sensor/status values).
    A container node (Factory/Line/Zone) has children that are further
    Objects. Checking node class lets us walk trees of any depth safely."""
    children = await node.get_children()
    if not children:
        return False
    for child in children:
        node_class = await child.read_node_class()
        # NodeClass.Variable == 2 ; NodeClass.Object == 1
        if node_class.value != 2:
            return False
    return True


async def _walk(node, results: dict):
    """Recursively descends the OPC-UA tree. Any node whose children are
    all Variables is treated as a machine/zone leaf and its readings are
    captured — this works for any depth (Factory>Line>Machine or
    Factory>Zone>Machine), not just a fixed 3-level hierarchy."""
    if await _is_leaf_machine_node(node):
        m_id = (await node.read_browse_name()).Name
        results[m_id] = {}
        params = await node.get_children()
        for param in params:
            name = (await param.read_browse_name()).Name
            value = await param.read_value()
            results[m_id][name] = value
        return

    children = await node.get_children()
    for child in children:
        await _walk(child, results)


async def read_all_nodes() -> dict:
    """
    Returns dict: {machine_id: {node_name: value}}
    Connects, walks the full tree regardless of depth, disconnects.
    """
    results = {}
    async with Client(url=settings.opcua_server_url) as client:
        root = client.nodes.root
        objects = await root.get_child(["0:Objects"])
        top_level = await objects.get_children()

        for node in top_level:
            name = (await node.read_browse_name()).Name
            if name == "Server":
                continue
            await _walk(node, results)

    return results


async def print_state():
    state = await read_all_nodes()
    for machine_id, params in state.items():
        print(f"\nMachine: {machine_id}")
        for k, v in params.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(print_state())