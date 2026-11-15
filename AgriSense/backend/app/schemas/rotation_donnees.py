"""Contrats de fusion des observations multi-sources pour la rotation."""
from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=2, max_length=60)
    domaine: str = Field(default="general", max_length=40)
    observed_at: datetime | date | None = None
    retrieved_at: datetime | None = None
    quality_status: str = Field(default="unverified", max_length=30)
    values: dict[str, Any] = Field(min_length=1, max_length=100)
    units: dict[str, str] = Field(default_factory=dict)
    dataset_id: str | None = Field(default=None, max_length=120)

    @field_validator("source", "domaine", "quality_status")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip().lower()


class RotationDataFusionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observations: list[SourceObservation] = Field(default_factory=list, max_length=100)
    inclure_donnees_parcelle: bool = True
    inclure_dernier_sol: bool = True
