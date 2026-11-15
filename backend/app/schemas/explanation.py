"""API contracts for explanations of already-computed agricultural results."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExplanationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "results": {
                        "<sortie_du_moteur>": (
                            "Remplacer ce texte par les résultats réels, inchangés."
                        )
                    },
                    "language": "fr",
                    "detail": "detailed",
                }
            ]
        },
    )

    results: dict[str, Any] = Field(
        description="Résultats déjà calculés; aucune décision ne sera recalculée par Groq."
    )
    language: str = Field(default="fr", min_length=2, max_length=10)
    detail: Literal["concise", "detailed"] = "detailed"


class GroundedRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    evidence: list[str] = Field(
        description="JSON Pointer(s) to non-empty values in the supplied results.",
    )


class ExplanationContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    agronomic_analysis: str
    economic_analysis: str
    water_analysis: str
    climate_risks: list[str]
    advantages: list[str]
    disadvantages: list[str]
    recommendations: list[GroundedRecommendation]
    limitations: list[str]


class ExplanationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    generated_at: str
    language: str
    category: Literal["general", "rotation", "scoring", "risks"]
    source_results_sha256: str
    usage: dict[str, int] | None = None


class ExplanationResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "provider": "groq",
                    "explanation": {
                        "summary": "<résumé fondé sur les résultats fournis>",
                        "agronomic_analysis": "<analyse agronomique>",
                        "economic_analysis": "<analyse économique ou indisponible>",
                        "water_analysis": "<analyse hydrique ou indisponible>",
                        "climate_risks": [],
                        "advantages": [],
                        "disadvantages": [],
                        "recommendations": [
                            {
                                "text": "<conseil relié aux données>",
                                "evidence": ["/chemin/json/pointer"],
                            }
                        ],
                        "limitations": ["<limites et données manquantes>"],
                    },
                    "metadata": {
                        "model": "<modèle configuré>",
                        "generated_at": "<horodatage ISO-8601>",
                        "language": "fr",
                        "category": "general",
                        "source_results_sha256": "<empreinte des résultats d'entrée>",
                        "usage": None,
                    },
                }
            ]
        },
    )

    success: Literal[True] = True
    provider: Literal["groq"] = "groq"
    explanation: ExplanationContent
    metadata: ExplanationMetadata


class ExplanationHealth(BaseModel):
    status: Literal["configured", "unconfigured"]
    provider: Literal["groq"] = "groq"
    model: str
    api_key_configured: bool
