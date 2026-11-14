from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

PRIORITY_KEYS = ("water", "yield", "soil_health", "profitability", "resilience", "pests", "sustainability")


class Priorities(BaseModel):
    """Importance de 0 (ignoré) à 5 (essentiel)."""

    water: int = Field(3, ge=0, le=5)
    yield_: int = Field(3, ge=0, le=5, alias="yield")
    soil_health: int = Field(3, ge=0, le=5)
    profitability: int = Field(3, ge=0, le=5)
    resilience: int = Field(3, ge=0, le=5)
    pests: int = Field(3, ge=0, le=5)
    sustainability: int = Field(3, ge=0, le=5)

    model_config = ConfigDict(populate_by_name=True)

    def as_dict(self) -> dict[str, int]:
        return self.model_dump(by_alias=True)


class Constraints(BaseModel):
    forbidden_crops: list[int] = []
    budget_tnd_per_ha: float | None = Field(default=None, ge=0)
    equipment_notes: str | None = None


class AnalysisCreate(BaseModel):
    parcel_id: int
    crop_codes: list[int] = Field(min_length=2)
    priorities: Priorities = Priorities()
    constraints: Constraints = Constraints()
    horizon_years: int = Field(4, ge=3, le=5)

    @field_validator("crop_codes")
    @classmethod
    def unique_codes(cls, codes):
        return list(dict.fromkeys(codes))


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parcel_id: int
    selected_crops: list
    priorities: dict
    constraints: dict
    horizon_years: int
    status: str
    result: dict
    created_at: datetime


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parcel_id: int
    horizon_years: int
    created_at: datetime


class SaveRotationIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    rotation_id: str


class SavedRotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    name: str
    rotation: dict
    created_at: datetime
