from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PolygonGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]

    @field_validator("coordinates")
    @classmethod
    def check_ring(cls, rings):
        if not rings or len(rings[0]) < 4:
            raise ValueError("Le polygone doit avoir au moins 3 sommets.")
        for ring in rings:
            if ring[0] != ring[-1]:
                raise ValueError("Chaque anneau du polygone doit être fermé.")
            for lon, lat, *_ in ring:
                if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                    raise ValueError("Coordonnées hors limites (WGS84 attendu : longitude, latitude).")
        return rings


class ParcelBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    agro_zone_id: str | None = None
    irrigation: Literal["none", "limited", "full"] = "none"
    current_rotation: list[int] | None = None
    notes: str | None = None


class ParcelCreate(ParcelBase):
    geometry: PolygonGeometry


class ParcelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    agro_zone_id: str | None = None
    irrigation: Literal["none", "limited", "full"] | None = None
    current_rotation: list[int] | None = None
    notes: str | None = None
    geometry: PolygonGeometry | None = None


class SoilProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    data_status: str
    depth_label: str | None
    ph: float | None
    clay_pct: float | None
    sand_pct: float | None
    silt_pct: float | None
    soc_g_kg: float | None
    nitrogen_g_kg: float | None
    bulk_density_g_cm3: float | None
    theta_fc: float | None
    theta_pwp: float | None
    sm_rootzone: float | None
    sm_measured_on: date | None
    created_at: datetime


class SoilLabInput(BaseModel):
    """Analyse saisie par l'agriculteur : toutes les valeurs sont optionnelles, rien n'est complété."""

    depth_label: str | None = None
    ph: float | None = Field(default=None, ge=0, le=14)
    clay_pct: float | None = Field(default=None, ge=0, le=100)
    sand_pct: float | None = Field(default=None, ge=0, le=100)
    silt_pct: float | None = Field(default=None, ge=0, le=100)
    soc_g_kg: float | None = Field(default=None, ge=0)
    nitrogen_g_kg: float | None = Field(default=None, ge=0)
    bulk_density_g_cm3: float | None = Field(default=None, gt=0, lt=2.65)
    theta_fc: float | None = Field(default=None, gt=0, lt=1)
    theta_pwp: float | None = Field(default=None, ge=0, lt=1)
    sm_rootzone: float | None = Field(default=None, ge=0, lt=1)
    sm_measured_on: date | None = None


class ParcelOut(ParcelBase):
    id: int
    geometry: dict
    area_ha: float
    centroid: dict
    created_at: datetime
    soil_profiles: list[SoilProfileOut] = []
