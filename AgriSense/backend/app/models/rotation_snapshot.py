"""Snapshots immuables des données utilisées par le moteur de rotation."""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RotationSnapshot(Base):
    __tablename__ = "rotation_data_snapshots"
    __table_args__ = (
        UniqueConstraint("parcelle_id", "version", name="uq_rotation_snapshot_parcelle_version"),
        Index("ix_rotation_snapshot_parcelle_created", "parcelle_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcelle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parcelles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    farmer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
