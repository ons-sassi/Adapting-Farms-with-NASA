"""Schemas de comparaison et de traçabilité des rotations."""
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.rotation_scoring import RotationSubScores, RotationScoringWeights


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=200)
    type_source: str = Field(min_length=1, max_length=60)
    date_donnee: date | None = None
    validee: bool | None = None
    reference: str | None = Field(default=None, max_length=500)


class RotationComparisonItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identifiant: str = Field(min_length=1, max_length=100)
    cultures: list[str] = Field(min_length=1, max_length=20)
    sous_scores: RotationSubScores
    preuves: dict[str, list[EvidenceInput]] = Field(default_factory=dict)
    commentaires: list[str] = Field(default_factory=list)


class RotationComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rotations: list[RotationComparisonItem] = Field(min_length=2, max_length=10)
    ponderations: RotationScoringWeights = Field(default_factory=RotationScoringWeights)
    minimum_dimensions_requises: int = Field(default=3, ge=1, le=6)
    fraicheur_max_jours: int | None = Field(default=None, ge=1, le=3650)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [item.identifiant.casefold() for item in self.rotations]
        if len(ids) != len(set(ids)):
            raise ValueError("Les identifiants de rotations doivent être uniques.")
        return self
