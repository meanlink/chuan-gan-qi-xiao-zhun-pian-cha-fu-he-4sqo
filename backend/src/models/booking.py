from sqlalchemy import String, JSON, Double, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base

class Booking(Base):
    __tablename__ = 'bookings'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    request_key: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(160))
    bath_id: Mapped[int] = mapped_column(ForeignKey('equipment.id'))
    standard_id: Mapped[int] = mapped_column(ForeignKey('equipment.id'))
    start_at: Mapped[float] = mapped_column(Double)
    end_at: Mapped[float] = mapped_column(Double)
    clean_minutes: Mapped[int] = mapped_column(Integer, default=30)
    stabilize_minutes: Mapped[int] = mapped_column(Integer, default=20)
    status: Mapped[str] = mapped_column(String(24), default='booked')
    reschedule_reason: Mapped[str] = mapped_column(String(400), default='')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    started_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    sealed_at: Mapped[float | None] = mapped_column(Double, nullable=True)

class Reading(Base):
    __tablename__ = 'readings'
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey('bookings.id'))
    sample: Mapped[str] = mapped_column(String(120))
    band: Mapped[str] = mapped_column(String(60))
    reference: Mapped[float] = mapped_column(Double)
    measured: Mapped[float] = mapped_column(Double)
    received_at: Mapped[float] = mapped_column(Double)

class AnalysisBatch(Base):
    __tablename__ = 'analysis_batches'
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_no: Mapped[str] = mapped_column(String(40), unique=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey('bookings.id'), unique=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    rows: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[float] = mapped_column(Double)
