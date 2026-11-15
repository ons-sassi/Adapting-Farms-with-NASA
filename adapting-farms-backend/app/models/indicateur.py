from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class IndicateurCalculation(Base):
    __tablename__ = "indicateur_calculations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parcelle_id: Mapped[int] = mapped_column(ForeignKey("parcelles.id", ondelete="CASCADE"), nullable=False, index=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    culture: Mapped[str] = mapped_column(String(160), nullable=False)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
