from datetime import datetime
from pydantic import BaseModel, Field
class CalculIndicateursCreate(BaseModel):
    culture: str = Field(min_length=1, max_length=160, description="Nom commun, code EcoPort ou nom scientifique")
    start: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date de fin exclue")
    sol_mesure: dict[str, float] | None = None
class CalculationResponse(BaseModel):
    id: int
    parcelle_id: int
    culture: str
    start_date: str | None
    end_date: str | None
    status: str
    result: dict | None
    error_message: str | None
    created_at: datetime
    model_config = {"from_attributes": True}
