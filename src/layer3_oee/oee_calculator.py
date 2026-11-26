"""
Computes OEE = Availability x Performance x Quality per line per interval.
Availability = run_time / planned_time
Performance = (ideal_cycle_time x total_units) / run_time
Quality = good_units / total_units

FIX (Availability/Performance stuck at 0%): calculate_availability() used
to sum EVERY DowntimeEvent ever logged for a line, with no time-window
filter, and subtract that all-time total from a single shift's
planned_minutes (480). Once more than one shift's worth of downtime had
ever been logged for a line (e.g. after seed_demo_oee_data.py inserts 5
shifts x 1-3 events each), the all-time sum always exceeded 480, so
run_time floored at 0 and Availability was permanently 0% for every line,
which cascaded into Performance also being 0% (it depends on run_time).
Quality was unaffected since it doesn't use downtime at all -- which is
exactly why Quality kept showing real numbers while Availability/
Performance didn't.

Now calculate_availability() takes an explicit [shift_start, shift_end)
window and only sums downtime events that actually overlap that window,
matching what "planned_minutes for this shift" is supposed to mean.
compute_and_store_oee() requires shift_start/shift_end to be passed in --
callers (the API, the seed script) must supply the shift window they're
computing OEE for.
"""
from datetime import datetime, timedelta
from src.layer3_oee.models import SessionLocal, OEERecord, DowntimeEvent, SKUCycleTime


def calculate_availability(line_id: str, planned_minutes: float,
                            shift_start: datetime, shift_end: datetime) -> float:
    """Only counts downtime events that overlap [shift_start, shift_end) --
    not the line's entire downtime history. An event overlaps the window if
    it starts before the window ends AND ends after the window starts."""
    session = SessionLocal()
    try:
        events = (session.query(DowntimeEvent)
                  .filter(DowntimeEvent.line_id == line_id)
                  .filter(DowntimeEvent.start_time < shift_end)
                  .filter(DowntimeEvent.end_time > shift_start)
                  .all())
    finally:
        session.close()

    downtime = 0.0
    for e in events:
        # Clip each event to the shift window in case it straddles the
        # boundary (started before shift_start or ends after shift_end),
        # so a long event isn't double-counted across two shifts.
        overlap_start = max(e.start_time, shift_start)
        overlap_end = min(e.end_time, shift_end)
        downtime += max((overlap_end - overlap_start).total_seconds() / 60, 0)

    run_time = max(planned_minutes - downtime, 0)
    return round(run_time / planned_minutes, 4) if planned_minutes > 0 else 0.0


def calculate_performance(total_units: int, run_time_minutes: float, product_sku: str) -> float:
    session = SessionLocal()
    sku = session.query(SKUCycleTime).filter(SKUCycleTime.product_sku == product_sku).first()
    session.close()
    if not sku or run_time_minutes <= 0:
        return 0.0
    ideal_output = (run_time_minutes * 60) / sku.ideal_cycle_time_seconds
    return round(min(total_units / ideal_output, 1.0), 4) if ideal_output > 0 else 0.0


def calculate_quality(good_units: int, total_units: int) -> float:
    if total_units <= 0:
        return 0.0
    return round(good_units / total_units, 4)


def compute_and_store_oee(factory_id, line_id, planned_minutes, total_units, good_units, product_sku,
                           shift_start: datetime = None, shift_end: datetime = None,
                           recorded_at: datetime = None):
    """...
    recorded_at: timestamp to store on the OEERecord. Defaults to
    shift_end (the moment the shift's data becomes available), NOT
    datetime.now() -- using now() meant all 5 rows a seed script wrote in
    quick succession got nearly identical timestamps, so "latest row"
    was non-deterministic and the OEE Analytics page could show any of
    them depending on Postgres's tiebreak. Using shift_end gives each
    shift a distinct, monotonic timestamp that reflects when the shift
    actually ended.
    """
    if shift_end is None:
        shift_end = datetime.now()
    if shift_start is None:
        shift_start = shift_end - timedelta(minutes=planned_minutes)
    if recorded_at is None:
        recorded_at = shift_end

    availability = calculate_availability(line_id, planned_minutes, shift_start, shift_end)
    run_time = planned_minutes * availability
    performance = calculate_performance(total_units, run_time, product_sku)
    quality = calculate_quality(good_units, total_units)
    oee = round(availability * performance * quality, 4)

    session = SessionLocal()
    record = OEERecord(
        factory_id=factory_id, line_id=line_id, timestamp=recorded_at,
        availability=availability, performance=performance, quality=quality, oee=oee
    )
    session.add(record)
    session.commit()
    session.close()

    return {"availability": availability, "performance": performance, "quality": quality, "oee": oee}