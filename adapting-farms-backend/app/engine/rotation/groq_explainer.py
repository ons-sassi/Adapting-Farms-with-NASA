"""Compatibility adapter for the existing rotation explanation endpoint."""

from fastapi import HTTPException

from app.schemas.explanation import ExplanationRequest
from app.services.llm.explanation_service import (
    ExplanationServiceError,
    explain_results,
)


async def generer_explication(
    donnees_rotation: dict,
    langue: str = "fr",
    niveau_detail: str = "detaille",
) -> dict:
    request = ExplanationRequest(
        results=donnees_rotation,
        language=langue,
        detail="concise" if niveau_detail == "court" else "detailed",
    )
    try:
        response = await explain_results(request, category="rotation")
    except ExplanationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_detail) from None

    content = response.explanation
    sections = [
        content.summary,
        content.agronomic_analysis,
        content.economic_analysis,
        content.water_analysis,
    ]
    sections.extend(content.climate_risks)
    sections.extend(content.advantages)
    sections.extend(content.disadvantages)
    sections.extend(
        f"{item.text} (preuves : {', '.join(item.evidence)})"
        for item in content.recommendations
    )
    sections.extend(content.limitations)
    return {
        "fournisseur": response.provider,
        "modele": response.metadata.model,
        "explication": "\n\n".join(section for section in sections if section),
        "usage": response.metadata.usage,
        "avertissement": (
            "Texte généré à partir des seules données fournies ; les calculs et le classement "
            "restent ceux du moteur déterministe."
        ),
    }
