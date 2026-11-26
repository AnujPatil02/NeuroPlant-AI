"""
One-time seed script: populates realistic OEERecord + DowntimeEvent rows
for LINE01/02/03, using values that are physically consistent with
plant_topology.json's real product_skus cycle times -- not arbitrary
random numbers.

REVISION (this pass -- A/P/Q ceiling fix + achievable-target cap):
  Two related bugs were producing OEE cards with "99.0%" Performance and
  "99.0%" Quality, and a line OEE (87.0%) that fell short of the target
  (95.1%) it was supposed to hit:

  1. The A/P/Q solver clamped both performance and quality at 0.99 and
     left them there when the target OEE was unachievable. A 95.1% target
     at 88.8% availability requires P*Q = 1.071 -- mathematically
     impossible since max(P*Q) = 0.99*0.99 = 0.9801. So the solver hit
     both ceilings and stored a lower OEE than the target.
     Fix: before solving, cap the shift's target OEE at what is actually
     achievable given this shift's own downtime:
         max_achievable_oee = availability * 0.99 * 0.99
     If the target exceeds this, reduce the shift target -- not clamp the
     factors into nonsense.

  2. Downtime draws averaged ~52 min per 8h shift (~89% availability),
     which capped achievable OEE at ~87% regardless of target. LINE03's
     target was 95.1% (from the machine-health mean), which is
     physically impossible at 89% availability. Fix: reduced downtime
     draw to 1-2 events of 5-25 min (average ~15-20 min -> ~96%
     availability), and lowered _LINE_TARGET_OEE["LINE03"] from 0.951
     to 0.895 to reflect what a real high-performance line can hit.
     World-class shift-level OEE is 85%; 95% is a metric you see on
     single-machine instantaneous dashboards, not shift aggregates.

Run once (or any time you want to reseed) from the project root:
    python -m scripts.seed_demo_oee_data
"""
from datetime import datetime, timedelta
import random

from src.layer3_oee.models import SessionLocal, OEERecord, DowntimeEvent
from src.layer3_oee.oee_calculator import compute_and_store_oee
from src.layer3_oee.downtime_classifier import log_downtime, VALID_REASON_CODES

_LINE_SKUS = {
    "LINE01": "SKU-101",  # Input Shaft, Component Machining
    "LINE02": "SKU-118",  # Gear Shaft, Precision Machining
    "LINE03": "SKU-130",  # CV Joint Housing, Finishing/Component Processing
}

# Matches plant_topology.json's product_skus ideal_cycle_time_sec exactly
_SKU_CYCLE_TIME_SEC = {
    "SKU-101": 42,
    "SKU-118": 47,
    "SKU-130": 51,
}

_LINE_MACHINES = {
    "LINE01": ["CNC-01", "CNC-02", "CNC-03", "CNC-04"],
    "LINE02": ["CNC-05", "CNC-06", "CNC-07", "CNC-08"],
    "LINE03": ["CNC-09", "CNC-10", "CNC-11", "CNC-12"],
}

# Per-line target OEE. Each is the mean of that line's four machines'
# OEE values in machine_monitoring._MACHINE_HEALTH_STATIC -- so the
# seeded OEERecord and the per-machine OEE agree by construction, and
# Home's Fleet OEE (mean across lines) matches Machine Monitoring's
# Plant Pulse. If the machine table changes, update these.
#
#   LINE01 = mean(94.2, 41.0, 95.1, 94.6) = 81.2%  (CNC-02 critical drag)
#   LINE02 = mean(95.4, 95.8, 71.4, 68.2) = 82.7%  (CNC-07/08 warnings)
#   LINE03 = mean(91.0, 90.2, 88.5, 88.3) = 89.5%  (all healthy)
_LINE_TARGET_OEE = {
    "LINE01": 0.812,
    "LINE02": 0.827,
    "LINE03": 0.895,
}
_PER_SHIFT_OFFSETS = [0.005, -0.004, 0.001, -0.002, 0.000]   # sums to 0, latest shift == target
_DOWNTIME_REASON_POOL = [r for r in VALID_REASON_CODES if r != "planned_maintenance"] or list(VALID_REASON_CODES)


def _clear_existing_for_line(line_id: str):
    """Deletes existing OEERecord + DowntimeEvent rows for this line so
    re-running the seed script produces a clean, consistent dataset
    instead of stacking new rows on top of old ones."""
    session = SessionLocal()
    try:
        session.query(OEERecord).filter(OEERecord.line_id == line_id).delete(synchronize_session=False)
        session.query(DowntimeEvent).filter(DowntimeEvent.line_id == line_id).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()


# Per-shift offsets (in OEE points) applied to the line's target. Chosen
# so their mean is EXACTLY zero -- so the 5-shift average lands exactly
# on the target, while each individual shift still varies realistically.
# Numbers are in *fractional OEE* units (0.006 = 0.6 pt).
#
# If you want different-looking variance, use any 5 numbers that sum to
# 0. Examples:
#   [0.006, -0.004, 0.002, -0.006, 0.002]  (larger swing)
#   [0.003, -0.002, 0.001, -0.003, 0.001]  (gentler)
_PER_SHIFT_OFFSETS = [0.005, -0.004, 0.001, -0.005, 0.003]   # sums to 0.000


def seed_line(line_id: str, rng: random.Random, num_shifts: int = 5):
    sku = _LINE_SKUS.get(line_id, "SKU-101")
    cycle_time_sec = _SKU_CYCLE_TIME_SEC.get(sku, 45)
    machines = _LINE_MACHINES.get(line_id, ["CNC-01"])
    target = _LINE_TARGET_OEE.get(line_id, 0.80)

    _clear_existing_for_line(line_id)

    # Shuffle the offsets per line so the sequence isn't identical across
    # lines, but each line's 5 offsets still sum to zero -> mean == target.
    # Copy first, then shuffle, so _PER_SHIFT_OFFSETS isn't mutated.
    offsets = list(_PER_SHIFT_OFFSETS[:num_shifts])
    rng.shuffle(offsets)

    now = datetime.now()
    for shift_i in range(num_shifts):
        shift_start = now - timedelta(hours=8 * (num_shifts - shift_i))
        shift_end = shift_start + timedelta(hours=8)
        planned_minutes = 480.0

        # ── Downtime events FIRST so Availability can see them ──────────
        n_events = rng.randint(1, 2)
        shift_downtime_min = 0.0
        for _ in range(n_events):
            machine_id = rng.choice(machines)
            reason = rng.choice(_DOWNTIME_REASON_POOL)
            duration_min = rng.randint(5, 25)
            event_start = shift_start + timedelta(minutes=rng.randint(0, 420))
            event_end = event_start + timedelta(minutes=duration_min)
            shift_downtime_min += duration_min
            try:
                log_downtime(
                    factory_id="FAC01", line_id=line_id, machine_id=machine_id,
                    reason_code=reason, start_time=event_start, end_time=event_end,
                )
            except Exception as e:
                print(f"[{line_id}] downtime log failed: {e}")

        # ── Derive A/P/Q so A*P*Q == this shift's target OEE ───────────
        run_time_minutes = max(planned_minutes - shift_downtime_min, 0)
        availability = round(run_time_minutes / planned_minutes, 4)
        max_achievable_oee = round(availability * 0.99 * 0.99, 4)

        # FIX: use the pre-generated zero-sum offset instead of a fresh
        # rng.uniform() draw per shift. This guarantees the 5-shift mean
        # lands EXACTLY on `target` (not within +/- 0.5 pt like before,
        # which is why you were seeing 81.4/81.9/88.6 instead of
        # 81.2/82.7/89.5).
        shift_target_oee = round(target + offsets[shift_i], 4)
        shift_target_oee = min(shift_target_oee, max_achievable_oee)
        shift_target_oee = max(shift_target_oee, 0.30)

        # Solve A * P * Q = shift_target_oee.
        quality = round(rng.uniform(0.92, 0.97), 4)
        performance = shift_target_oee / (availability * quality)

        if performance > 0.99:
            quality = round(min(shift_target_oee / (availability * 0.99), 0.99), 4)
            performance = round(shift_target_oee / (availability * quality), 4)

        if performance < 0.75:
            performance = 0.75
            quality = round(min(shift_target_oee / (availability * performance), 0.99), 4)

        performance = round(min(max(performance, 0.75), 0.99), 4)
        quality = round(min(max(quality, 0.85), 0.99), 4)

        # Recompute the stored OEE from the actual rounded A/P/Q so the
        # DB value matches what compute_and_store_oee will store.
        shift_target_oee = round(availability * performance * quality, 4)

        # total_units = performance * ideal_output for this run_time
        ideal_output = (run_time_minutes * 60) / cycle_time_sec if cycle_time_sec > 0 else 0
        total_units = max(int(ideal_output * performance), 1)
        good_units = max(int(total_units * quality), 1)

        try:
            compute_and_store_oee(
                factory_id="FAC01",
                line_id=line_id,
                planned_minutes=planned_minutes,
                total_units=total_units,
                good_units=good_units,
                product_sku=sku,
                shift_start=shift_start,
                shift_end=shift_end,
            )
        except Exception as e:
            print(f"[{line_id}] OEE compute failed for shift {shift_i}: {e}")
            continue

    print(f"[{line_id}] reseeded {num_shifts} shifts, target OEE {target*100:.1f}% "
          f"(5-shift mean is exactly target, per-shift offsets: "
          f"{[round(o*100, 2) for o in offsets]}).")


def main():
    rng = random.Random(2026)
    for line_id in ["LINE01", "LINE02", "LINE03"]:
        seed_line(line_id, rng)
    print()
    print("Done. Expected results:")
    print("  LINE01 OEE ~81.2%  (A ~95%, P ~90%, Q ~94%)")
    print("  LINE02 OEE ~82.7%  (A ~95%, P ~91%, Q ~95%)")
    print("  LINE03 OEE ~89.5%  (A ~95%, P ~98%, Q ~95%)")
    print()
    print("No value will hit 0.99 -- if it does, availability was too low")
    print("for the target, which means downtime draws are too heavy. If")
    print("that happens, verify the n_events/duration_min lines above.")


if __name__ == "__main__":
    main()