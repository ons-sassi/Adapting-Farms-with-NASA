from fastapi import APIRouter
from app.api.v1 import (
    auth, health, parcelles, sol,
    explanations,
    indicateurs_cultures_liste, indicateurs_culture_detail,
    indicateurs_calcul, indicateurs_resultats, indicateurs_historique,
    indicateurs_calcul_detail, agri_external_data,
    rotation, rotation_cultures, rotation_regles, rotation_generation,
    rotation_scoring, rotation_comparaison, rotation_preparation,
    rotation_explication, rotation_donnees, rotation_snapshots,
    rotation_snapshot_audit, rotation_sous_scores, rotation_ponderation, rotation_finalisation,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router)
api_router.include_router(parcelles.router)
api_router.include_router(sol.router)
api_router.include_router(indicateurs_cultures_liste.router)
api_router.include_router(indicateurs_culture_detail.router)
api_router.include_router(indicateurs_calcul.router)
api_router.include_router(indicateurs_resultats.router)
api_router.include_router(indicateurs_historique.router)
api_router.include_router(indicateurs_calcul_detail.router)
api_router.include_router(agri_external_data.router)
api_router.include_router(explanations.router)

# Modules de rotation : contexte, catalogue, exclusions, génération, scoring,
# préparation, explications Groq, fusion, snapshots, audit et sous-scores.
for module in (
    rotation, rotation_cultures, rotation_regles, rotation_generation,
    rotation_scoring, rotation_comparaison, rotation_preparation,
    rotation_explication, rotation_donnees, rotation_snapshots,
    rotation_snapshot_audit, rotation_sous_scores, rotation_ponderation, rotation_finalisation,
):
    api_router.include_router(module.router)
