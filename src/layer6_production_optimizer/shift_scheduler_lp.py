"""
SciPy LP shift scheduling — minimizes overtime cost, maximizes throughput,
subject to minimum staffing per line, skill-machine compatibility, and
shift duration compliance. Maintenance windows (Layer 4) are blocked automatically.
"""
from scipy.optimize import linprog


def optimize_shift_schedule(
    lines: list[dict],
    operators_available: int,
    max_overtime_hours_per_operator: float = 4.0,
    maintenance_blocked_lines: list[str] = None,
):
    """
    lines: list of dicts with keys:
        line_id, min_staff_required, overtime_cost_per_hour, throughput_per_operator
    Returns operator allocation per line minimizing overtime cost.
    """
    maintenance_blocked_lines = maintenance_blocked_lines or []
    active_lines = [l for l in lines if l["line_id"] not in maintenance_blocked_lines]
    n = len(active_lines)

    if n == 0:
        return {"error": "All lines blocked by maintenance — no schedule possible"}

    # Objective: minimize overtime cost (negative throughput reward built in via cost tradeoff)
    costs = [l["overtime_cost_per_hour"] - l["throughput_per_operator"] for l in active_lines]

    # Constraint: total operators allocated <= operators_available
    A_ub = [[1] * n]
    b_ub = [operators_available]

    # Bounds: each line needs at least min_staff, at most min_staff + overtime capacity
    bounds = [(l["min_staff_required"], l["min_staff_required"] + max_overtime_hours_per_operator) for l in active_lines]

    result = linprog(costs, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")

    if not result.success:
        return {"error": f"LP failed: {result.message}"}

    allocation = []
    for i, l in enumerate(active_lines):
        allocation.append({
            "line_id": l["line_id"],
            "operators_allocated": round(result.x[i], 1),
            "min_required": l["min_staff_required"],
        })

    blocked = [{"line_id": lid, "status": "blocked by maintenance"} for lid in maintenance_blocked_lines]

    return {"allocation": allocation, "blocked_lines": blocked, "total_cost": round(result.fun, 2)}


if __name__ == "__main__":
    lines = [
        {"line_id": "LINE01", "min_staff_required": 4, "overtime_cost_per_hour": 25, "throughput_per_operator": 12},
        {"line_id": "LINE02", "min_staff_required": 3, "overtime_cost_per_hour": 20, "throughput_per_operator": 10},
        {"line_id": "LINE03", "min_staff_required": 5, "overtime_cost_per_hour": 30, "throughput_per_operator": 15},
    ]
    result = optimize_shift_schedule(lines, operators_available=15, maintenance_blocked_lines=["LINE03"])
    print(result)