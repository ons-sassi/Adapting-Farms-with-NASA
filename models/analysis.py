from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class ClimateCache(Base):
    """Séries journalières NASA POWER mises en cache (données réelles téléchargées)."""

    __tablename__ = "climate_cache"
    __table_args__ = (UniqueConstraint("lat_key", "lon_key", "start_date", "end_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lat_key: Mapped[float] = mapped_column(Float)
    lon_key: Mapped[float] = mapped_column(Float)
    start_date: Mapped[str] = mapped_column(String(8))
    end_date: Mapped[str] = mapped_column(String(8))
    elevation_m: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Analysis(TimestampMixin, Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id", ondelete="CASCADE"), index=True)
    selected_crops: Mapped[list] = mapped_column(JSON)
    priorities: Mapped[dict] = mapped_column(JSON)
    constraints: Mapped[dict] = mapped_column(JSON)
    horizon_years: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="done")
    result: Mapped[dict] = mapped_column(JSON)


class SavedRotation(TimestampMixin, Base):
    __tablename__ = "saved_rotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    rotation: Mapped[dict] = mapped_column(JSON)
