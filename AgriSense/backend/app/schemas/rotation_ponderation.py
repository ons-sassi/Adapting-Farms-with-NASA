"""Schémas de pondération multicritère selon les priorités du fermier."""
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Priorities(StrictModel):
    economie_eau: float = Field(default=50, ge=0, le=100)
    revenu: float = Field(default=50, ge=0, le=100)
    fourrage: float = Field(default=0, ge=0, le=100)
    erosion: float = Field(default=50, ge=0, le=100)
    matiere_organique: float = Field(default=50, ge=0, le=100)
    azote: float = Field(default=50, ge=0, le=100)
    simplicite: float = Field(default=50, ge=0, le=100)

class Subscores(StrictModel):
    eau: float | None = Field(default=None, ge=0, le=1)
    climat_thermique: float | None = Field(default=None, ge=0, le=1)
    fertilite_sol: float | None = Field(default=None, ge=0, le=1)
    protection_erosion: float | None = Field(default=None, ge=0, le=1)
    dynamique_vegetative: float | None = Field(default=None, ge=0, le=1)
    compatibilite_succession: float | None = Field(default=None, ge=0, le=1)

class WeightedScoringRequest(StrictModel):
    priorites: Priorities
    sous_scores: Subscores
    seuil_couverture: float = Field(default=0.70, ge=0, le=1)

    @model_validator(mode="after")
    def require_priority_or_default(self):
        return self
