"""Logs and classifies downtime events by reason code."""
from datetime import datetime
from src.layer3_oee.models import SessionLocal, DowntimeEvent

VALID_REASON_CODES = [
    "planned_maintenance", "unplanned_breakdown", "changeover",
    "material_shortage", "quality_hold", "operator_absence"
]


def log_downtime(factory_id, line_id, machine_id, reason_code, start_time, end_time):
    if reason_code not in VALID_REASON_CODES:
        raise ValueError(f"Invalid reason_code. Must be one of {VALID_REASON_CODES}")

    duration = (end_time - start_time).total_seconds() / 60
    session = SessionLocal()
    event = DowntimeEvent(
        factory_id=factory_id, line_id=line_id, machine_id=machine_id,
        reason_code=reason_code, start_time=start_time, end_time=end_time,
        duration_minutes=round(duration, 2)
    )
    session.add(event)
    session.commit()
    session.close()
    return duration


def get_downtime_pareto(line_id: str, days: int = 7):
    """Returns downtime minutes grouped by reason_code — for Pareto chart."""
    session = SessionLocal()
    events = session.query(DowntimeEvent).filter(DowntimeEvent.line_id == line_id).all()
    session.close()

    pareto = {}
    for e in events:
        pareto[e.reason_code] = pareto.get(e.reason_code, 0) + e.duration_minutes
    return dict(sorted(pareto.items(), key=lambda x: x[1], reverse=True))