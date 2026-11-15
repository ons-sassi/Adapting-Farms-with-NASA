"""Contrat d'entrée pour la génération d'explications de rotations par Groq."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class RotationExplanationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    donnees_rotation: dict[str, Any] = Field(
        ...,
        description=(
            "Résultats déjà calculés par le backend : cultures, scores, critères, "
            "preuves, contraintes et comparaison éventuelle. Groq ne les recalcule pas."
        ),
    )
    langue: str = Field(default="fr", min_length=2, max_length=10)
    niveau_detail: str = Field(default="detaille", pattern="^(court|detaille)$")
