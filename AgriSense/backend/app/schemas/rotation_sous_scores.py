"""Schemas de calcul déterministe des six sous-scores agronomiques."""
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class WaterInputs(StrictModel):
    et0_daily_mm: list[float] | None = Field(default=None, min_length=1, max_length=500)
    effective_rainfall_mm: float | None = Field(default=None, ge=0)
    awc_mm_per_m: float | None = Field(default=None, gt=0, description="Capacité utile disponible en mm par mètre de sol")
    p_fao56: float | None = Field(default=None, ge=0, le=1)
    rsm_ratio: float | None = Field(default=None, ge=0)
    twi_norm: float | None = Field(default=None, ge=0, le=1)
    northness: float | None = Field(default=None, ge=-1, le=1)

class ThermalInputs(StrictModel):
    gdd_available: float | None = Field(default=None, ge=0)
    heat_days_after_yield_formation: int | None = Field(default=None, ge=0)
    cold_days_during_initial_phase: int | None = Field(default=None, ge=0)

class SoilInputs(StrictModel):
    ph_soil: float | None = Field(default=None, ge=0, le=14)
    exploitable_soil_depth_m: float | None = Field(default=None, ge=0)
    soc_norm: float | None = Field(default=None, ge=0, le=1)

class ErosionInputs(StrictModel):
    ls_norm: float | None = Field(default=None, ge=0, le=1)
    rainfall_erosivity_norm: float | None = Field(default=None, ge=0, le=1)

class HistoryInputs(StrictModel):
    vci_mean: float | None = Field(default=None, ge=0, le=1)
    evi_peak_trend_norm: float | None = Field(default=None, ge=-1, le=1)
    esi_mean: float | None = Field(default=None, ge=0, le=1)

class PreviousCrop(StrictModel):
    family: str = Field(min_length=1, max_length=100)
    n_fixer: bool | None = None
    root_depth_max_m: float | None = Field(default=None, ge=0)

class CandidateCrop(StrictModel):
    identifiant: str = Field(min_length=1, max_length=100)
    nom: str = Field(min_length=1, max_length=150)
    exclusion_status: str = Field(description="PASS uniquement pour calculer les sous-scores")
    kc_daily: list[float] | None = Field(default=None, min_length=1, max_length=500)
    gdd_maturity: float | None = Field(default=None, gt=0)
    ph_min: float | None = Field(default=None, ge=0, le=14)
    ph_opt: float | None = Field(default=None, ge=0, le=14)
    ph_max: float | None = Field(default=None, ge=0, le=14)
    root_depth_max_m: float | None = Field(default=None, gt=0)
    n_fixer: bool | None = None
    kc_ini: float | None = Field(default=None, ge=0)
    underground_harvest: bool | None = None
    family: str | None = Field(default=None, max_length=100)
    previous_crops: list[PreviousCrop] | None = Field(default=None, max_length=2, description="Ordre chronologique : c(t-1), puis c(t-2). [] signifie historique connu vide ; null signifie inconnu.")

    @model_validator(mode="after")
    def validate_ph_range(self):
        vals=(self.ph_min,self.ph_opt,self.ph_max)
        if all(v is not None for v in vals) and not (self.ph_min < self.ph_opt < self.ph_max):
            raise ValueError("Les bornes pH doivent respecter ph_min < ph_opt < ph_max.")
        return self

class RotationSubscoreRequest(StrictModel):
    hydrique: WaterInputs = Field(default_factory=WaterInputs)
    thermique: ThermalInputs = Field(default_factory=ThermalInputs)
    sol: SoilInputs = Field(default_factory=SoilInputs)
    erosion: ErosionInputs = Field(default_factory=ErosionInputs)
    historique: HistoryInputs = Field(default_factory=HistoryInputs)
    cultures: list[CandidateCrop] = Field(min_length=1, max_length=50)
    provenance: dict[str, list[str]] = Field(default_factory=dict, description="Sources/proofs per dimension; informational only")

    @model_validator(mode="after")
    def validate_et0_kc_alignment(self):
        if self.hydrique.et0_daily_mm is not None:
            for crop in self.cultures:
                if crop.kc_daily is not None and len(crop.kc_daily) != len(self.hydrique.et0_daily_mm):
                    raise ValueError(f"ET0 et Kc doivent avoir la même longueur pour {crop.identifiant}.")
        return self
