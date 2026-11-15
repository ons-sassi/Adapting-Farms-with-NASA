"""Audit de disponibilité des données nécessaires au scoring des rotations.

Cet audit ne calcule aucun sous-score agronomique : il indique les observations
présentes/manquantes afin d'éviter de fabriquer des valeurs ou des formules.
"""
from __future__ import annotations

from typing import Any

DIMENSION_FIELDS = {
    "eau": {
        "label": "Disponibilité et efficacité de l'eau",
        "description": "Informations d'irrigation, source d'eau et observations hydriques.",
    },
    "climat_thermique": {
        "label": "Adaptation thermique et climatique",
        "description": "Résultats climatiques/thermiques datés pour la parcelle.",
    },
    "fertilite_sol": {
        "label": "Qualité et fertilité du sol",
        "description": "Analyse de sol avec paramètres physico-chimiques.",
    },
    "protection_erosion": {
        "label": "Protection contre l'érosion",
        "description": "Pente et informations de sol utiles à l'évaluation de l'érosion.",
    },
    "dynamique_vegetative": {
        "label": "Dynamique végétative historique",
        "description": "Historique d'indicateurs de végétation associé à la parcelle.",
    },
    "compatibilite_succession": {
        "label": "Compatibilité des successions culturales",
        "description": "Historique cultural daté ou saisonnier de la parcelle.",
    },
}


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _result_keys(value: Any, prefix: str = "") -> set[str]:
    """Collecte les noms de clés imbriquées sans interpréter leurs valeurs."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            found.add(normalized)
            found.update(_result_keys(child, f"{prefix}{normalized}."))
    elif isinstance(value, list):
        for child in value[:100]:
            found.update(_result_keys(child, prefix))
    return found


def audit_rotation_data(parcel: Any, soils: list[Any], calculations: list[Any]) -> dict:
    latest_soil = soils[0] if soils else None
    soil_fields = (
        "ph", "organic_matter_percent", "texture", "nitrogen_mg_kg",
        "phosphorus_mg_kg", "potassium_mg_kg", "salinity_ds_m",
        "limestone_percent", "cec_cmol_kg",
    )
    soil_available = [name for name in soil_fields if latest_soil and _present(getattr(latest_soil, name, None))]

    indicator_keys: set[str] = set()
    completed_calculations = []
    for item in calculations:
        if (getattr(item, "status", "") or "").lower() == "completed" and _present(getattr(item, "result", None)):
            completed_calculations.append(item)
            indicator_keys.update(_result_keys(item.result))

    def indicator_matches(tokens: tuple[str, ...]) -> bool:
        return any(any(token in key for token in tokens) for key in indicator_keys)

    history = list(getattr(parcel, "cultures", []) or [])
    irrigation = _present(getattr(parcel, "irrigation_type", None)) and str(parcel.irrigation_type).lower() not in {"none", "unknown", "inconnu"}
    water_source = _present(getattr(parcel, "water_source", None))
    slope = _present(getattr(parcel, "slope_percent", None))

    evidence = {
        "eau": {
            "available": irrigation or water_source or indicator_matches(("water", "eau", "soil_moisture", "smap", "precipitation", "rainfall")),
            "fields": (["irrigation_type"] if irrigation else []) + (["water_source"] if water_source else []),
            "indicator_match": indicator_matches(("water", "eau", "soil_moisture", "smap", "precipitation", "rainfall")),
            "missing": [name for name, ok in (("irrigation_type", irrigation), ("water_source", water_source)) if not ok],
        },
        "climat_thermique": {
            "available": indicator_matches(("temperature", "temp", "tmin", "tmax", "degree_day", "gdd", "frost", "gel", "heat", "chaleur")),
            "fields": [],
            "indicator_match": indicator_matches(("temperature", "temp", "tmin", "tmax", "degree_day", "gdd", "frost", "gel", "heat", "chaleur")),
            "missing": ["observations thermiques/climatiques identifiables dans les résultats"],
        },
        "fertilite_sol": {
            "available": bool(soil_available),
            "fields": soil_available,
            "indicator_match": False,
            "missing": [name for name in soil_fields if name not in soil_available],
        },
        "protection_erosion": {
            "available": slope or bool(soil_available),
            "fields": (["slope_percent"] if slope else []) + soil_available,
            "indicator_match": False,
            "missing": [name for name, ok in (("slope_percent", slope), ("soil_analysis", bool(soil_available))) if not ok],
        },
        "dynamique_vegetative": {
            "available": bool(completed_calculations) and indicator_matches(("ndvi", "evi", "vci", "vegetation", "lai", "fapar", "ndwi")),
            "fields": [],
            "indicator_match": indicator_matches(("ndvi", "evi", "vci", "vegetation", "lai", "fapar", "ndwi")),
            "missing": ["indicateurs de végétation (NDVI/EVI/VCI/LAI…)"],
        },
        "compatibilite_succession": {
            "available": len(history) > 0,
            "fields": ["crop_history"] if history else [],
            "indicator_match": False,
            "missing": ["historique cultural de la parcelle"] if not history else [],
        },
    }

    dimensions = {}
    for key, info in DIMENSION_FIELDS.items():
        row = evidence[key]
        dimensions[key] = {
            "libelle": info["label"],
            "description": info["description"],
            "donnees_disponibles": bool(row["available"]),
            "champs_observes": row["fields"],
            "correspondance_indicateurs": row["indicator_match"],
            "donnees_manquantes": row["missing"],
            "sous_score": None,
            "statut_sous_score": "A_CALCULER" if row["available"] else "DONNEES_INSUFFISANTES",
        }

    available_count = sum(item["donnees_disponibles"] for item in dimensions.values())
    return {
        "dimensions": dimensions,
        "resume": {
            "dimensions_total": len(dimensions),
            "dimensions_avec_donnees": available_count,
            "dimensions_sans_donnees": len(dimensions) - available_count,
            "couverture_donnees": round(available_count / len(dimensions), 4),
            "analyses_sol_disponibles": len(soils),
            "calculs_indicateurs_termines": len(completed_calculations),
            "historique_cultural_entrees": len(history),
        },
        "donnees_source": {
            "analyse_sol_la_plus_recente": {
                "id": getattr(latest_soil, "id", None),
                "date_prelevement": getattr(latest_soil, "sampled_at", None).isoformat() if latest_soil and getattr(latest_soil, "sampled_at", None) else None,
                "source": getattr(latest_soil, "source", None),
            } if latest_soil else None,
            "indicateurs": [
                {"id": item.id, "culture": item.culture, "periode": {"debut": item.start_date, "fin": item.end_date}, "created_at": item.created_at.isoformat() if item.created_at else None}
                for item in completed_calculations[:20]
            ],
            "historique_cultural": [
                {"culture": item.crop_name, "saison": item.season}
                for item in history
            ],
        },
        "decision": "PRET_A_CALCULER_CERTAINES_DIMENSIONS" if available_count else "DONNEES_A_COMPLETER",
        "limites": [
            "Cet audit vérifie la présence de données, pas leur qualité agronomique ni leur validité scientifique.",
            "Aucun sous-score n'est calculé ici; les formules de scoring doivent être définies et validées avant implémentation.",
            "La présence d'un indicateur dans un résultat JSON ne garantit pas son unité, sa période ou sa résolution spatiale.",
            "Les données externes non rattachées explicitement à cette parcelle ne sont pas utilisées.",
        ],
    }
