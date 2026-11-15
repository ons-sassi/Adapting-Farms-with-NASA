"""Agrégation explicable des sous-scores selon les priorités déclarées.

La matrice est une convention produit explicite, pas une formule fournie par
« les règles.pdf ». Les objectifs économiques et de simplicité ne sont pas
mesurés par les six sous-scores agronomiques : ils sont signalés comme non couverts.
"""
from __future__ import annotations

DIMENSIONS = (
    "eau", "climat_thermique", "fertilite_sol",
    "protection_erosion", "dynamique_vegetative", "compatibilite_succession",
)
# Contribution de chaque priorité à chacune des dimensions agronomiques.
MATRIX = {
    "economie_eau": {"eau": .55, "climat_thermique": .10, "fertilite_sol": .05, "protection_erosion": .10, "dynamique_vegetative": .05, "compatibilite_succession": .15},
    "revenu": {"eau": .15, "climat_thermique": .25, "fertilite_sol": .20, "protection_erosion": .05, "dynamique_vegetative": .15, "compatibilite_succession": .20},
    "fourrage": {"eau": .15, "climat_thermique": .20, "fertilite_sol": .10, "protection_erosion": .10, "dynamique_vegetative": .30, "compatibilite_succession": .15},
    "erosion": {"eau": .05, "climat_thermique": .05, "fertilite_sol": .10, "protection_erosion": .60, "dynamique_vegetative": .10, "compatibilite_succession": .10},
    "matiere_organique": {"eau": .05, "climat_thermique": .05, "fertilite_sol": .30, "protection_erosion": .20, "dynamique_vegetative": .15, "compatibilite_succession": .25},
    "azote": {"eau": .05, "climat_thermique": .05, "fertilite_sol": .25, "protection_erosion": .05, "dynamique_vegetative": .10, "compatibilite_succession": .50},
    "simplicite": {"eau": .20, "climat_thermique": .15, "fertilite_sol": .15, "protection_erosion": .10, "dynamique_vegetative": .15, "compatibilite_succession": .25},
}
UNMEASURED_PRIORITY = {"revenu": "Un score économique de marché (marge, coûts, rendement, prix) est requis.", "simplicite": "Les contraintes de matériel, main-d'œuvre et complexité des itinéraires sont requises."}

def calculate_weighted_score(priorities: dict, scores: dict, coverage_threshold: float=.70) -> dict:
    p = {k: max(0.0, min(100.0, float(v))) for k, v in priorities.items()}
    p_total = sum(p.values())
    if p_total <= 0:
        raise ValueError("Au moins une priorité doit être supérieure à zéro.")
    raw = {d: sum((p.get(goal, 0.0)/p_total)*MATRIX[goal][d] for goal in MATRIX) for d in DIMENSIONS}
    total_w = sum(raw.values())
    weights = {d: raw[d]/total_w for d in DIMENSIONS}
    available = {d: float(scores[d]) for d in DIMENSIONS if scores.get(d) is not None}
    if any(not 0 <= v <= 1 for v in available.values()):
        raise ValueError("Chaque sous-score disponible doit être compris entre 0 et 1.")
    coverage = sum(weights[d] for d in available)
    weighted = sum(weights[d]*available[d] for d in available)
    normalized = weighted/coverage if coverage > 0 else None
    warnings = [f"Sous-score manquant : {d}" for d in DIMENSIONS if d not in available]
    unsupported = [f"{goal}: {UNMEASURED_PRIORITY[goal]}" for goal, value in p.items() if value > 0 and goal in UNMEASURED_PRIORITY]
    status = "COMPLET" if coverage >= .999999 else ("PARTIEL" if coverage > 0 else "INSUFFISANT")
    return {
        "statut": status,
        "score_global": round(normalized, 6) if normalized is not None and coverage >= coverage_threshold else None,
        "score_provisoire": round(normalized, 6) if normalized is not None else None,
        "couverture_ponderation": round(coverage, 6),
        "seuil_couverture": coverage_threshold,
        "poids": {k: round(v, 6) for k, v in weights.items()},
        "contributions": {k: round(weights[k]*available[k], 6) for k in available},
        "donnees_manquantes": warnings,
        "priorites_non_mesurees_par_les_six_sous_scores": unsupported,
        "methode": "matrice_transparente_priorites_fermier_v1",
        "avertissement": "La matrice de correspondance est une convention configurable du produit, pas une formule chiffrée du PDF. Le score global n'est publié que si la couverture atteint le seuil.",
    }
