from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class Crop(Base):
    """Caractéristiques d'une culture (jamais des mesures de parcelle). Valeur absente = NULL."""

    __tablename__ = "crops"

    eco_port_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    scientific_name: Mapped[str] = mapped_column(String(160), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    common_names: Mapped[str | None] = mapped_column(String)
    family: Mapped[str | None] = mapped_column(String(80))
    category: Mapped[str | None] = mapped_column(String)
    life_span: Mapped[str | None] = mapped_column(String(60))
    n_fixer: Mapped[bool | None] = mapped_column(Boolean)
    level: Mapped[str] = mapped_column(String(60), index=True)

    ph_min: Mapped[float | None] = mapped_column(Float)
    ph_max: Mapped[float | None] = mapped_column(Float)
    ph_opt: Mapped[float | None] = mapped_column(Float)

    kc_ini: Mapped[float | None] = mapped_column(Float)
    kc_mid: Mapped[float | None] = mapped_column(Float)
    kc_end: Mapped[float | None] = mapped_column(Float)
    stage_ini_days: Mapped[int | None] = mapped_column(Integer)
    stage_dev_days: Mapped[int | None] = mapped_column(Integer)
    stage_mid_days: Mapped[int | None] = mapped_column(Integer)
    stage_late_days: Mapped[int | None] = mapped_column(Integer)
    root_depth_max_m: Mapped[float | None] = mapped_column(Float)
    depletion_fraction_p: Mapped[float | None] = mapped_column(Float)

    t_base: Mapped[float | None] = mapped_column(Float)
    t_upper: Mapped[float | None] = mapped_column(Float)
    gdd_maturity: Mapped[float | None] = mapped_column(Float)
    gdd_yield_start: Mapped[float | None] = mapped_column(Float)

    cycle_min_days: Mapped[float | None] = mapped_column(Float)
    cycle_max_days: Mapped[float | None] = mapped_column(Float)
    ecology: Mapped[dict | None] = mapped_column(JSON)  # plages EcoCrop brutes
    sources: Mapped[dict | None] = mapped_column(JSON)  # source par groupe de paramètres

    calendars: Mapped[list["CropCalendar"]] = relationship(back_populates="crop", cascade="all, delete-orphan")

    @property
    def rotation_eligible(self) -> bool:
        return self.level.startswith("1a") or self.level.startswith("1b")


class CropCalendar(Base):
    __tablename__ = "crop_calendars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eco_port_code: Mapped[int] = mapped_column(ForeignKey("crops.eco_port_code", ondelete="CASCADE"), index=True)
    country: Mapped[str] = mapped_column(String(2))
    zone_id: Mapped[str] = mapped_column(String(10))
    zone_name: Mapped[str] = mapped_column(String(160))
    usage: Mapped[str | None] = mapped_column(String)
    sow_start_month: Mapped[int] = mapped_column(Integer)
    sow_start_day: Mapped[int] = mapped_column(Integer)
    sow_end_month: Mapped[int] = mapped_column(Integer)
    sow_end_day: Mapped[int] = mapped_column(Integer)
    harvest_start_month: Mapped[int] = mapped_column(Integer)
    harvest_start_day: Mapped[int] = mapped_column(Integer)
    harvest_end_month: Mapped[int] = mapped_column(Integer)
    harvest_end_day: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(60))

    crop: Mapped[Crop] = relationship(back_populates="calendars")


class DataSource(Base):
    __tablename__ = "data_sources"

    source_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    reference: Mapped[str] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(String)
    accessed_on: Mapped[str | None] = mapped_column(String(20))
    used_for: Mapped[str | None] = mapped_column(String)
