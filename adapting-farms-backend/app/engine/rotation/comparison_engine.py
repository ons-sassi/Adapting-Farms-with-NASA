"""Comparaison des rotations et audit de couverture des preuves.

L'indicateur de couverture des preuves n'est pas une probabilité de réussite.
Aucun coefficient de fiabilité scientifique n'est inventé ici.
"""
from __future__ import annotations
from datetime import date
from app.engine.rotation.scoring_engine import DIMENSIONS, rank_rotations


def _evidence_audit(rotation: dict, max_age_days: int | None, today: date) -> dict:
    scores = rotation.get("sous_scores", {})
    evidence = rotation.get("preuves", {}) or {}
    available = [key for key in DIMENSIONS if scores.get(key) is not None]
    documented = []
    validated = []
    undated = []
    stale = []
    by_dimension = {}
    for key in DIMENSIONS:
        items = evidence.get(key, []) or []
        normalized = []
        for item in items:
            if hasattr(item, "model_dump"):
                item = item.model_dump(mode="json")
            elif isinstance(item, dict):
                item = dict(item)
            else:
                item = {"source": str(item), "type_source": "non_precise", "date_donnee": None, "validee": None}
            raw_date = item.get("date_donnee")
            if isinstance(raw_date, str) and raw_date:
                try:
                    raw_date = date.fromisoformat(raw_date)
                except ValueError:
                    raw_date = None
            if raw_date is not None and not isinstance(raw_date, date):
                raw_date = None
            if raw_date is not None:
                age = max((today - raw_date).days, 0)
                item["age_jours"] = age
                if max_age_days is not None and age > max_age_days:
                    stale.append(key)
            else:
                item["age_jours"] = None
                if item.get("source"):
                    undated.append(key)
            normalized.append(item)
        has_evidence = bool(normalized)
        has_validated = any(item.get("validee") is True for item in normalized)
        if key in available and has_evidence:
            documented.append(key)
        if key in available and has_validated:
            validated.append(key)
        by_dimension[key] = {
            "score_disponible": scores.get(key) is not None,
            "nombre_preuves": len(normalized),
            "au_moins_une_preuve_validee": has_validated,
            "preuves": normalized,
        }
    coverage = len(documented) / len(available) if available else None
    return {
        "dimensions_avec_score": len(available),
        "dimensions_documentees": len(documented),
        "dimensions_avec_preuve_validee": len(validated),
        "couverture_preuves": round(coverage, 4) if coverage is not None else None,
        "dimensions_sans_preuve": [key for key in available if key not in documented],
        "dimensions_avec_preuve_non_datee": sorted(set(undated)),
        "dimensions_avec_donnees_perimees": sorted(set(stale)),
        "controle_fraicheur": "APPLIQUE" if max_age_days is not None else "NON_DEMANDE",
        "detail": by_dimension,
        "interpretation": (
            "La couverture mesure la présence de pièces justificatives pour les dimensions scorées. "
            "Elle ne constitue pas une probabilité de succès agronomique."
        ),
    }


def compare_rotations(rotations: list[dict], weights: dict, min_dimensions: int,
                      max_age_days: int | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    # Convert evidence objects to JSON-safe dicts for the scoring engine.
    score_inputs = []
    audits = {}
    for item in rotations:
        copied = dict(item)
        copied["sous_scores"] = item["sous_scores"]
        copied["preuves"] = {}
        for key, values in (item.get("preuves") or {}).items():
            copied["preuves"][key] = [
                value.model_dump(mode="json") if hasattr(value, "model_dump") else value
                for value in values
            ]
        score_inputs.append(copied)
        audits[item["identifiant"]] = _evidence_audit(copied, max_age_days, today)

    ranked = rank_rotations(score_inputs, weights, min_dimensions)
    pairwise = []
    for i in range(len(ranked)):
        for j in range(i + 1, len(ranked)):
            a, b = ranked[i], ranked[j]
            sa, sb = a["score_global"], b["score_global"]
            differences = {}
            for key in DIMENSIONS:
                va = a["detail_sous_scores"][key]["score"]
                vb = b["detail_sous_scores"][key]["score"]
                differences[key] = round(va - vb, 4) if va is not None and vb is not None else None
            pairwise.append({
                "rotation_a": a["identifiant"],
                "rotation_b": b["identifiant"],
                "ecart_score_global": round(sa - sb, 4) if sa is not None and sb is not None else None,
                "ecart_points_sur_100": round((sa - sb) * 100, 2) if sa is not None and sb is not None else None,
                "avantages_par_dimension": differences,
                "comparaison_possible": sa is not None and sb is not None
                    and a["statut"] != "INSUFFISANT" and b["statut"] != "INSUFFISANT",
            })
    return {
        "methode_classement": "moyenne_ponderee_renormalisee_sur_dimensions_disponibles",
        "ponderations": weights,
        "rotations_classees": ranked,
        "audit_confiance": audits,
        "comparaisons_paires": pairwise,
        "limites": [
            "La couverture des preuves n'est pas une probabilité de réussite.",
            "La fraîcheur n'est évaluée que si fraicheur_max_jours est fournie.",
            "Les scores d'entrée doivent avoir été calculés et validés en amont.",
            "Les règles d'exclusion restent prioritaires sur le classement.",
        ],
    }
