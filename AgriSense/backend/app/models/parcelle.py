from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Parcelle(Base):
    __tablename__ = "parcelles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    farmer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    irrigation_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default="none", server_default="none"
    )
    water_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    slope_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Champs saisis dans l'interface web (migration 008)
    zone: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_crop: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )

    cultures: Mapped[list["ParcelleCulture"]] = relationship(
        back_populates="parcelle", cascade="all, delete-orphan"
    )
    constraints: Mapped[list["ParcelleConstraint"]] = relationship(
        back_populates="parcelle", cascade="all, delete-orphan"
    )


class ParcelleCulture(Base):
    __tablename__ = "parcelle_cultures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parcelle_id: Mapped[int] = mapped_column(
        ForeignKey("parcelles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    crop_name: Mapped[str] = mapped_column(String(120), nullable=False)
    season: Mapped[str] = mapped_column(String(40), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    parcelle: Mapped["Parcelle"] = relationship(back_populates="cultures")


class ParcelleConstraint(Base):
    __tablename__ = "parcelle_constraints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parcelle_id: Mapped[int] = mapped_column(
        ForeignKey("parcelles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    constraint_type: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parcelle: Mapped["Parcelle"] = relationship(back_populates="constraints")
