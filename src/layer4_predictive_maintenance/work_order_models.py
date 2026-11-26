"""
Layer 4 - Work Order persistence model.

Backs the "Create Work Order" action on the Digital Twin / Machine
Inspector.

CONFIRMED against your real src/layer3_oee/models.py: it exports Base,
SessionLocal, engine, and init_db() at module level, and engine is built
from settings.postgres_url (not settings.database_url, which never
existed -- that was an earlier incorrect guess on my part before I had
the real file). This version imports Base/SessionLocal directly from
models.py with no fallback branch needed, since the real file guarantees
both names exist.

SETUP: WorkOrder is registered on the SAME Base as OEERecord/
DowntimeEvent/SKUCycleTime, so it's created automatically the next time
you run:
    python -m src.layer3_oee.models
(i.e. models.py's own `if __name__ == "__main__": init_db()` block) --
no separate provisioning step for this file. Just re-run that once after
adding this file to your project, and the work_orders table will exist
alongside the other three tables.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime

from src.layer3_oee.models import Base, SessionLocal, engine


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(String, nullable=False, index=True)
    line_id = Column(String, nullable=True)
    fault_type = Column(String, nullable=True)
    priority_score = Column(Float, nullable=False, default=0.5)
    rul_days = Column(Float, nullable=True)
    assigned_technician_slot = Column(String, nullable=True)
    estimated_parts_required = Column(String, nullable=True)
    status = Column(String, nullable=False, default="open")  # open | in_progress | completed | cancelled
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(String, nullable=True)


def create_work_order(machine_id: str, line_id: str = None, fault_type: str = None,
                       priority_score: float = 0.5, rul_days: float = None,
                       assigned_technician_slot: str = None,
                       estimated_parts_required: str = None, notes: str = None) -> dict:
    """Creates a work order record and returns it as a dict.

    Self-provisioning: calls Base.metadata.create_all(engine) before every
    insert. SQLAlchemy's create_all() is a no-op for tables that already
    exist (it checks first), so this costs nothing on the common case and
    means the work_orders table no longer needs a manual one-off setup
    command -- it's created automatically the first time this function
    runs, same as how the button behaves the very first time it's clicked."""
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        wo = WorkOrder(
            machine_id=machine_id, line_id=line_id, fault_type=fault_type,
            priority_score=priority_score, rul_days=rul_days,
            assigned_technician_slot=assigned_technician_slot,
            estimated_parts_required=estimated_parts_required, notes=notes,
        )
        session.add(wo)
        session.commit()
        session.refresh(wo)
        return {
            "id": wo.id, "machine_id": wo.machine_id, "line_id": wo.line_id,
            "fault_type": wo.fault_type, "priority_score": wo.priority_score,
            "rul_days": wo.rul_days, "assigned_technician_slot": wo.assigned_technician_slot,
            "estimated_parts_required": wo.estimated_parts_required,
            "status": wo.status, "created_at": str(wo.created_at),
        }
    except Exception as e:
        session.rollback()
        raise RuntimeError(f"Work order creation failed: {e}") from e
    finally:
        session.close()


def get_work_orders_for_machine(machine_id: str, status: str = None) -> list:
    """Returns open (or filtered-status) work orders for a machine, most
    recent first -- used by the Machine Inspector to show "No open work
    order" vs an actual work order once one exists."""
    session = SessionLocal()
    try:
        query = session.query(WorkOrder).filter(WorkOrder.machine_id == machine_id)
        if status:
            query = query.filter(WorkOrder.status == status)
        rows = query.order_by(WorkOrder.created_at.desc()).all()
        return [{
            "id": r.id, "machine_id": r.machine_id, "line_id": r.line_id,
            "fault_type": r.fault_type, "priority_score": r.priority_score,
            "rul_days": r.rul_days, "status": r.status, "created_at": str(r.created_at),
        } for r in rows]
    except Exception:
        return []
    finally:
        session.close()