"""Schemas de la requête d'évaluation des règles d'exclusion agronomique."""
from datetime import date
from pydantic import BaseModel, Field, ConfigDict

class DailyWorkabilityObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date
    surface_saturation: float | None = Field(default=None, ge=0)
    surface_temp_k: float | None = Field(default=None, ge=0)

class CropTraitsOverride(BaseModel):
    """Traits absents du catalogue actuel; None signifie information inconnue."""
    model_config = ConfigDict(extra="forbid")
    sensitive_to_late_frost: bool | None = None
    sensitive_to_waterlogging: bool | None = None
    root_or_tuber_crop: bool | None = None

class ExclusionRuleEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    culture_identifiant: str = Field(min_length=1, max_length=160)
    traits: CropTraitsOverride = Field(default_factory=CropTraitsOverride)

    # Règle 1 - Cycle thermique
    ratio_gdd: float | None = Field(default=None, ge=0)

    # Règle 2 - pH
    soil_ph: float | None = Field(default=None, ge=0, le=14)
    ph_score: float | None = Field(default=None, ge=0, le=1)

    # Règle 3 - Gel tardif
    tpi: float | None = None
    last_spring_frost: date | None = None
    sowing_window_start: date | None = None
    microclimate_frost_delay_days: int | None = Field(default=None, ge=7, le=10)

    # Règle 4 - Excès d'eau
    twi_high: bool | None = None
    rsm_gt_1_critical_duration: bool | None = None

    # Règle 5 - Texture
    clay_ratio: float | None = Field(default=None, ge=0, le=1)

    # Règle 6 - Praticabilité (les jours doivent couvrir les fenêtres concernées)
    sowing_workability_days: list[DailyWorkabilityObservation] = Field(default_factory=list)
    harvest_workability_days: list[DailyWorkabilityObservation] = Field(default_factory=list)
    surface_saturation_max_threshold: float | None = Field(default=None, ge=0)
    n_min_chantier: int | None = Field(default=None, ge=1, le=30)

    # Règle 7 - Rupture sanitaire
    previous_families: list[str] = Field(default_factory=list, max_length=10)
    vci_decline_despite_normal_weather: bool | None = None
