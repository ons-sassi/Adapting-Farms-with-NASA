from pydantic import BaseModel, Field
from typing import Any

class MarketItem(BaseModel):
    crop: str
    yield_t_ha: float | None = Field(default=None, ge=0)
    price_per_t: float | None = Field(default=None, ge=0)
    variable_cost_per_ha: float | None = Field(default=None, ge=0)
    source: str | None = None
    observed_at: str | None = None
    currency: str = "TND"

class EconomicRequest(BaseModel):
    market: list[MarketItem]
    area_ha: float = Field(gt=0)
    rotations: list[dict[str, Any]] = Field(min_length=1, max_length=20)
    weights: dict[str, float] = Field(default_factory=dict)

class OptimizeRequest(BaseModel):
    strategies: list[dict[str, Any]] = Field(min_length=1, max_length=3)
    priorities: dict[str, float] = Field(default_factory=dict)
    minimum_dimensions: int = Field(default=3, ge=1, le=10)

class SimulationRequest(BaseModel):
    rotations: list[dict[str, Any]] = Field(min_length=1, max_length=20)
    climate: dict[str, float] = Field(default_factory=dict, description="Variations explicites en % ou °C, fournies par l'utilisateur")
    economics: dict[str, float] = Field(default_factory=dict, description="Variations explicites en %")

class ReliabilityRequest(BaseModel):
    snapshot_id: int | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    local_validation: dict[str, Any] | None = None

class FeedbackRequest(BaseModel):
    recommendation_id: str
    rating: int = Field(ge=1, le=5)
    comment: str | None = None
    accepted: bool | None = None
    local_adjustments: dict[str, Any] = Field(default_factory=dict)

class ImportRequest(BaseModel):
    dataset: str = Field(pattern="^(market|cultures|soil_observations)$")
    csv_content: str = Field(min_length=1, max_length=2_000_000)
