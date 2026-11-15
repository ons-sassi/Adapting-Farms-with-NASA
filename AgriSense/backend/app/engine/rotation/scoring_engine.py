"""Scoring transparent des rotations à partir de sous-scores fournis et justifiés.

Les six sous-scores sont attendus sur [0, 1]. Ce moteur ne calcule pas les
sous-scores agronomiques bruts : il agrège uniquement les valeurs validées
transmises par les collecteurs/moteurs spécialisés.
"""
from __future__ import annotations

DIMENSIONS = (
    "eau",
    "climat_thermique",
    "fertilite_sol",
    "protection_erosion",
    "dynamique_vegetative",
    "compatibilite_succession",
)

LABELS = {
    "eau": "Disponibilité et efficacité de l'eau",
    "climat_thermique": "Adaptation thermique et climatique",
    "fertilite_sol": "Qualité et fertilité du sol",
    "protection_erosion": "Protection contre l'érosion",
    "dynamique_vegetative": "Dynamique végétative historique",
    "compatibilite_succession": "Compatibilité des successions culturales",
}


def score_rotation(rotation: dict, weights: dict, minimum_dimensions: int) -> dict:
    scores = rotation["sous_scores"]
    weighted_sum = 0.0
    available_weight = 0.0
    total_weight = sum(float(weights.get(key, 0)) for key in DIMENSIONS)
    details = {}
    missing = []

    for key in DIMENSIONS:
        value = scores.get(key)
        weight = float(weights.get(key, 0))
        if value is None:
            missing.append(key)
            details[key] = {
                "libelle": LABELS[key],
                "score": None,
                "ponderation": weight,
                "statut": "NON_DISPONIBLE",
                "preuves": rotation.get("preuves", {}).get(key, []),
            }
            continue
        weighted_sum += float(value) * weight
        available_weight += weight
        details[key] = {
            "libelle": LABELS[key],
            "score": round(float(value), 4),
            "ponderation": weight,
            "statut": "DISPONIBLE",
            "preuves": rotation.get("preuves", {}).get(key, []),
        }

    available_count = sum(scores.get(key) is not None for key in DIMENSIONS)
    global_score = (weighted_sum / available_weight) if available_weight > 0 else None
    coverage = (available_weight / total_weight) if total_weight > 0 else 0.0
    if available_count < minimum_dimensions or global_score is None:
        status = "INSUFFISANT"
    elif missing:
        status = "PARTIEL"
    else:
        status = "COMPLET"

    return {
        "identifiant": rotation["identifiant"],
        "cultures": rotation["cultures"],
        "score_global": round(global_score, 4) if global_score is not None else None,
        "score_sur_100": round(global_score * 100, 2) if global_score is not None else None,
        "couverture_ponderations": round(coverage, 4),
        "dimensions_disponibles": available_count,
        "dimensions_manquantes": missing,
        "statut": status,
        "detail_sous_scores": details,
        "preuves": rotation.get("preuves", {}),
        "commentaires": rotation.get("commentaires", []),
        "interpretation": (
            "Score calculé uniquement sur les dimensions disponibles; les pondérations "
            "ont été renormalisées sur ces dimensions. Les dimensions manquantes ne valent pas zéro."
        ),
    }


def rank_rotations(rotations: list[dict], weights: dict, minimum_dimensions: int) -> list[dict]:
    results = [score_rotation(item, weights, minimum_dimensions) for item in rotations]
    results.sort(
        key=lambda item: (
            item["score_global"] is not None and item["statut"] != "INSUFFISANT",
            item["score_global"] if item["score_global"] is not None else -1,
            item["couverture_ponderations"],
        ),
        reverse=True,
    )
    for index, item in enumerate(results, start=1):
        item["rang"] = index if item["score_global"] is not None and item["statut"] != "INSUFFISANT" else None
    return results
