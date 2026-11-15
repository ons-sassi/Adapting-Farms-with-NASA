from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


IrrigationType = Literal["none", "drip", "sprinkler", "surface", "other"]


class ParcelleBase(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    area_ha: float = Field(gt=0, le=100000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    geometry: dict[str, Any] | None = None
    irrigation_type: IrrigationType = "none"
    water_source: str | None = Field(default=None, max_length=100)
    slope_percent: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude et longitude doivent être fournies ensemble")
        return self


class ParcelleCreate(ParcelleBase):
    pass


class ParcelleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    area_ha: float | None = Field(default=None, gt=0, le=100000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    geometry: dict[str, Any] | None = None
    irrigation_type: IrrigationType | None = None
    water_source: str | None = Field(default=None, max_length=100)
    slope_percent: float | None = Field(default=None, ge=0, le=100)


class ParcelleResponse(ParcelleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    farmer_id: int
    created_at: datetime
    updated_at: datetime


class CultureCreate(BaseModel):
    crop_name: str = Field(min_length=1, max_length=120)
    season: str = Field(min_length=1, max_length=40)
    notes: str | None = None


class CultureResponse(CultureCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parcelle_id: int
    created_at: datetime


class ConstraintCreate(BaseModel):
    constraint_type: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1)


class ConstraintResponse(ConstraintCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parcelle_id: int
