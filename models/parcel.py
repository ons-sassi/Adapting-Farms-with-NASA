from datetime import date

from geoalchemy2 import Geometry
from sqlalchemy import JSON, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin


class Parcel(TimestampMixin, Base):
    __tablename__ = "parcels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    geometry = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="TN")
    agro_zone_id: Mapped[str | None] = mapped_column(String(10))
    irrigation: Mapped[str] = mapped_column(String(20), default="none")  # none | limited | full
    current_rotation: Mapped[list | None] = mapped_column(JSON)  # liste de codes EcoPort, la plus récente en dernier
    notes: Mapped[str | None] = mapped_column(Text)

    soil_profiles: Mapped[list["SoilProfile"]] = relationship(
        back_populates="parcel", cascade="all, delete-orphan", order_by="SoilProfile.id.desc()"
    )


class SoilProfile(TimestampMixin, Base):
    """Propriétés du sol d'une parcelle. `data_status` : measured (analyse labo) ou estimated (SoilGrids)."""

    __tablename__ = "soil_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(40))  # lab | soilgrids
    data_status: Mapped[str] = mapped_column(String(20))  # measured | estimated
    depth_label: Mapped[str | None] = mapped_column(String(40))
    ph: Mapped[float | None] = mapped_column(Float)
    clay_pct: Mapped[float | None] = mapped_column(Float)
    sand_pct: Mapped[float | None] = mapped_column(Float)
    silt_pct: Mapped[float | None] = mapped_column(Float)
    soc_g_kg: Mapped[float | None] = mapped_column(Float)
    nitrogen_g_kg: Mapped[float | None] = mapped_column(Float)
    bulk_density_g_cm3: Mapped[float | None] = mapped_column(Float)
    theta_fc: Mapped[float | None] = mapped_column(Float)  # m3/m3
    theta_pwp: Mapped[float | None] = mapped_column(Float)  # m3/m3
    sm_rootzone: Mapped[float | None] = mapped_column(Float)  # m3/m3, mesure réelle si disponible
    sm_measured_on: Mapped[date | None] = mapped_column(Date)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    parcel: Mapped[Parcel] = relationship(back_populates="soil_profiles")
