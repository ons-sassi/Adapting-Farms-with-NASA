from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


SoilSource = Literal["manual", "laboratory", "soilgrids"]


class SoilAnalysisCreate(BaseModel):
    parcelle_id: int = Field(gt=0)
    ph: float | None = Field(default=None, ge=0, le=14)
    organic_matter_percent: float | None = Field(default=None, ge=0, le=100)
    texture: str | None = Field(default=None, max_length=100)
    nitrogen_mg_kg: float | None = Field(default=None, ge=0)
    phosphorus_mg_kg: float | None = Field(default=None, ge=0)
    potassium_mg_kg: float | None = Field(default=None, ge=0)
    salinity_ds_m: float | None = Field(default=None, ge=0)
    limestone_percent: float | None = Field(default=None, ge=0, le=100)
    cec_cmol_kg: float | None = Field(default=None, ge=0)
    sampled_at: date | None = None
    source: SoilSource = "manual"
    notes: str | None = None


class SoilAnalysisUpdate(BaseModel):
    ph: float | None = Field(default=None, ge=0, le=14)
    organic_matter_percent: float | None = Field(default=None, ge=0, le=100)
    texture: str | None = Field(default=None, max_length=100)
    nitrogen_mg_kg: float | None = Field(default=None, ge=0)
    phosphorus_mg_kg: float | None = Field(default=None, ge=0)
    potassium_mg_kg: float | None = Field(default=None, ge=0)
    salinity_ds_m: float | None = Field(default=None, ge=0)
    limestone_percent: float | None = Field(default=None, ge=0, le=100)
    cec_cmol_kg: float | None = Field(default=None, ge=0)
    sampled_at: date | None = None
    source: SoilSource | None = None
    notes: str | None = None


class SoilAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parcelle_id: int
    ph: float | None
    organic_matter_percent: float | None
    texture: str | None
    nitrogen_mg_kg: float | None
    phosphorus_mg_kg: float | None
    potassium_mg_kg: float | None
    salinity_ds_m: float | None
    limestone_percent: float | None
    cec_cmol_kg: float | None
    sampled_at: date | None
    source: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
