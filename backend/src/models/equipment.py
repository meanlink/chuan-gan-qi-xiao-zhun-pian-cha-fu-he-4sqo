from sqlalchemy import String, Double, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base

class Equipment(Base):
    __tablename__ = 'equipment'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))  # bath 恒温槽 / standard 标准仪

class Downtime(Base):
    __tablename__ = 'downtimes'
    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey('equipment.id'))
    start_at: Mapped[float] = mapped_column(Double)
    end_at: Mapped[float] = mapped_column(Double)
    reason: Mapped[str] = mapped_column(String(200))
    request_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
