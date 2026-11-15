"""Schemas de génération de séquences pluriannuelles de cultures."""
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, model_validator

class RotationCandidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identifiant: str = Field(min_length=1, max_length=160)
    # Les preuves nécessaires aux 7 règles. Les absences restent UNKNOWN.
    traits: dict = Field(default_factory=dict)
    rule_inputs: dict = Field(default_factory=dict)
    # Fenêtre officielle connue pour la parcelle (dates récurrentes MM-DD).
    sowing_window_start: str = Field(pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
    sowing_window_end: str = Field(pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
    # Durée du cycle issue d'une source vérifiée ou d'une validation agronomique.
    cycle_days: int = Field(gt=0, le=500)
    # True uniquement si la récolte souterraine est confirmée pour cette culture.
    underground_harvest: bool | None = None

class RotationGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    horizon_years: int = Field(default=4, ge=3, le=4)
    candidates: list[RotationCandidateInput] = Field(min_length=2, max_length=80)
    start_date: date
    max_sequences: int = Field(default=3, ge=1, le=10)
    sensitive_family_return_years: int = Field(default=4, ge=3, le=4)
    min_intercrop_days: int = Field(default=15, ge=15, le=60)
    initial_soc_norm: float | None = Field(default=None, ge=0, le=1)
    initial_erosion_risk: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_candidates(self):
        if len({c.identifiant.casefold() for c in self.candidates}) != len(self.candidates):
            raise ValueError("Les identifiants de cultures doivent être uniques.")
        return self
