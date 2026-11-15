"""Analyses de rotation et rotations enregistrées depuis l'interface web (migration 008)."""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppAnalysis(Base):
    __tablename__ = "app_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    parcelle_id: Mapped[int] = mapped_column(ForeignKey("parcelles.id", ondelete="CASCADE"))
    request: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class AppSavedRotation(Base):
    __tablename__ = "app_saved_rotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("app_analyses.id", ondelete="CASCADE"))
    rotation_key: Mapped[str] = mapped_column(String(20), nullable=False)
    rotation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    saved_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
