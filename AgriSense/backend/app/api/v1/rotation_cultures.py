"""Catalogue agronomique pour la préparation des rotations de cultures."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/rotation", tags=["Rotation - Catalogue agronomique"])

ROTATION_FIELDS = (
    "famille", "n_fixer", "saison", "tbase", "t_upper", "gdd_requis",
    "kc", "zr_mm", "ph_min", "ph_max", "ph_opt", "duree_cycle",
    "semis", "recolte", "seuil_praticable",
)
NOT_YET_AVAILABLE_FIELDS = (
    "sensibilite_gel", "sensibilite_exces_eau", "sensibilite_secheresse",
    "culture_racine_ou_tubercule", "profondeur_racinaire_minimale_m",
)

def _build_crop_item(crop: dict[str, Any]) -> dict[str, Any]:
    from bd.cultures import get_culture
    profile, profile_error = None, None
    try:
        profile = get_culture(str(crop.get("code")))
    except (KeyError, ValueError, RuntimeError) as exc:
        profile_error = str(exc)
    missing = list(ROTATION_FIELDS) if profile is None else [
        field for field in ROTATION_FIELDS if profile.get(field) is None
    ]
    missing.extend(NOT_YET_AVAILABLE_FIELDS)
    return {
        "code": crop.get("code"),
        "nom_scientifique": crop.get("nom_scientifique"),
        "noms_communs": crop.get("noms", []),
        "famille_catalogue": crop.get("famille"),
        "saison_catalogue": crop.get("saison"),
        "profil_agronomique": profile,
        "champs_manquants": sorted(set(missing)),
        "profil_complet_pour_rotation": not missing,
        "erreur_profil": profile_error,
        "source": "MySQL / bd.cultures",
    }

@router.get("/cultures/catalogue")
def lister_catalogue_rotation(
    limit: int = Query(default=200, ge=1, le=1000),
    current_user=Depends(get_current_user),
):
    try:
        from bd.cultures import lister_cultures
        crops = lister_cultures()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Catalogue des cultures indisponible : {exc}") from exc
    items = [_build_crop_item(crop) for crop in crops[:limit]]
    return {
        "total_disponible": len(crops),
        "total_retourne": len(items),
        "total_profils_complets": sum(item["profil_complet_pour_rotation"] for item in items),
        "cultures": items,
        "source": "MySQL / bd.cultures",
        "notice": "Les champs absents restent inconnus. Les profils incomplets ne doivent pas valider une rotation.",
    }

@router.get("/cultures/{identifiant}")
def obtenir_culture_rotation(
    identifiant: str,
    current_user=Depends(get_current_user),
):
    try:
        from bd.cultures import get_culture
        profile = get_culture(identifiant)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Catalogue des cultures indisponible : {exc}") from exc
    missing = [field for field in ROTATION_FIELDS if profile.get(field) is None]
    missing.extend(NOT_YET_AVAILABLE_FIELDS)
    return {
        "profil_agronomique": profile,
        "champs_manquants": sorted(set(missing)),
        "profil_complet_pour_rotation": not missing,
        "source": profile.get("source"),
        "notice": "Les caractéristiques non présentes dans la base ne sont pas estimées par cette API.",
    }
