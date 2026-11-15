from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class SoilAnalysis(Base):
    __tablename__ = "soil_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parcelle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parcelles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    organic_matter_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    texture: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nitrogen_mg_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    phosphorus_mg_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    potassium_mg_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    salinity_ds_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    limestone_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    cec_cmol_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    sampled_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
