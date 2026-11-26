"""SQLAlchemy models for OEE records, downtime events, and SKU cycle times.

FIX (work_orders table missing, v2): the first fix imported
work_order_models at MODULE level, which caused a circular import --
work_order_models.py does `from src.layer3_oee.models import Base,
SessionLocal`, and while this file was still mid-import, Python handed
back the partially-built module (WorkOrder not yet defined in it),
raising ImportError.

Real fix: import work_order_models INSIDE init_db() instead. By the time
init_db() is called, this file has already finished loading top-to-bottom
(Base, SessionLocal, engine all exist), so work_order_models.py's import
of them succeeds cleanly with no cycle. This import's only purpose is to
register the WorkOrder class on Base.metadata before create_all() runs.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.config.settings import settings

Base = declarative_base()


class OEERecord(Base):
    __tablename__ = "oee_records"
    id = Column(Integer, primary_key=True)
    factory_id = Column(String)
    line_id = Column(String)
    timestamp = Column(DateTime)
    availability = Column(Float)
    performance = Column(Float)
    quality = Column(Float)
    oee = Column(Float)


class DowntimeEvent(Base):
    __tablename__ = "downtime_events"
    id = Column(Integer, primary_key=True)
    factory_id = Column(String)
    line_id = Column(String)
    machine_id = Column(String)
    reason_code = Column(String)  # planned_maintenance, unplanned_breakdown, changeover, material_shortage, quality_hold, operator_absence
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_minutes = Column(Float)


class SKUCycleTime(Base):
    __tablename__ = "sku_cycle_times"
    id = Column(Integer, primary_key=True)
    product_sku = Column(String, unique=True)
    ideal_cycle_time_seconds = Column(Float)


engine = create_engine(settings.postgres_url)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    # Imported HERE, not at module level -- avoids the circular import
    # (see docstring above). Only job is to register WorkOrder on
    # Base.metadata before create_all() runs.
    from src.layer4_predictive_maintenance.work_order_models import WorkOrder  # noqa: F401
    Base.metadata.create_all(engine)
    print("Tables created: oee_records, downtime_events, sku_cycle_times, work_orders")


if __name__ == "__main__":
    init_db()