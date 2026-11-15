"""Schemas d'entrée/sortie du scoring agronomique des rotations."""
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RotationSubScores(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eau: float | None = Field(default=None, ge=0, le=1)
    climat_thermique: float | None = Field(default=None, ge=0, le=1)
    fertilite_sol: float | None = Field(default=None, ge=0, le=1)
    protection_erosion: float | None = Field(default=None, ge=0, le=1)
    dynamique_vegetative: float | None = Field(default=None, ge=0, le=1)
    compatibilite_succession: float | None = Field(default=None, ge=0, le=1)


class RotationScoreInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identifiant: str = Field(min_length=1, max_length=100)
    cultures: list[str] = Field(min_length=1, max_length=20)
    sous_scores: RotationSubScores
    preuves: dict[str, list[str]] = Field(default_factory=dict)
    commentaires: list[str] = Field(default_factory=list)


class RotationScoringWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eau: float = Field(default=1, ge=0)
    climat_thermique: float = Field(default=1, ge=0)
    fertilite_sol: float = Field(default=1, ge=0)
    protection_erosion: float = Field(default=1, ge=0)
    dynamique_vegetative: float = Field(default=1, ge=0)
    compatibilite_succession: float = Field(default=1, ge=0)

    @model_validator(mode="after")
    def at_least_one_weight(self):
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("Au moins une pondération doit être strictement positive.")
        return self


class RotationScoringRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rotations: list[RotationScoreInput] = Field(min_length=1, max_length=10)
    ponderations: RotationScoringWeights = Field(default_factory=RotationScoringWeights)
    minimum_dimensions_requises: int = Field(default=3, ge=1, le=6)
