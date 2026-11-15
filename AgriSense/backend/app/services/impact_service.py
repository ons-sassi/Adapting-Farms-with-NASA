"""
Service d'impact environnemental (CŒUR). Appelé par : le pipeline de rotation, l'endpoint /impact,
le chatbot, l'explication Groq. Il ne dépend d'aucun d'eux.
"""
from __future__ import annotations

import json

from app.engine.impact import compute_impact, format_message, load_params


class ImpactService:
    def __init__(self, params: dict | None = None, id_map: dict | None = None, baseline_crop: str = "wheat",
                 names: dict | None = None):
        self.names = names or {}            # id -> nom affiché dans les messages (ex. "fava" -> "fève")
        self.params = params or load_params()
        self.id_map = id_map or {}          # id catalogue du cœur -> id utilisé dans impact_params.json
        self.baseline_crop = baseline_crop  # rotation « classique » = même céréale chaque saison

    def _ids(self, seq):
        return [self.id_map.get(c, c) for c in seq]

    def for_rotation(self, sequence, *, hectares: float = 1.0, n_rate=None, baseline=None, names=None) -> dict:
        prop = self._ids(sequence)
        base = self._ids(baseline) if baseline else [self.baseline_crop] * len(prop)
        return compute_impact(prop, base, hectares=hectares, n_rate=n_rate, params=self.params, names=names or self.names)

    def summarize(self, r: dict, lang: str = "fr") -> dict:
        """Version compacte et sûre : c'est CE dict qui entre dans le contexte de réponse."""
        if not r.get("ok") or "water" not in r:
            return {"available": False, "missing_data": r.get("missing_data", []), "lines": format_message(r, lang)}
        c = r["co2e"]
        return {
            "available": True, "sequence": r["proposed"], "baseline": r["baseline"], "hectares": r["hectares"],
            "water_saved_litres": r["water"]["saved_litres"],
            "nitrogen_saved_kg": r["nitrogen"]["saved_kg"],
            "co2e_saved_kg_field": c["field_n2o_kg"],
            "co2e_saved_kg_with_production": c["with_production_kg"],
            "n_rate_is_example": r["nitrogen"]["rate_is_example"],
            "warnings": r["warnings"], "assumptions": r["assumptions"], "sources": r["sources"],
            "lines": format_message(r, lang),
        }

    def evaluate(self, sequence, **kw) -> dict:
        lang = kw.pop("lang", "fr")
        return self.summarize(self.for_rotation(sequence, **kw), lang)

    def enrich_ranking(self, rotations: list, *, key: str = "sequence", **kw) -> list:
        """Ajoute rotation['impact'] à chaque rotation classée par le moteur (aucun score n'est modifié)."""
        for rot in rotations:
            seq = rot.get(key)
            if seq:
                rot["impact"] = self.evaluate(seq, **kw)
        return rotations

    @staticmethod
    def prompt_block(summary: dict, lang: str = "fr") -> str:
        """Bloc à ajouter au prompt de l'explication : le LLM reformule, il ne calcule pas."""
        facts = {k: v for k, v in summary.items() if k != "lines"}
        rules = (
            "Règles : utilise UNIQUEMENT les chiffres de ce bloc, sans les modifier ni en inventer ; "
            "présente-les comme indicatifs ; si n_rate_is_example est vrai, précise que la dose d'azote est un exemple ; "
            "si available est faux, dis que l'impact ne peut pas être chiffré pour ces cultures."
        )
        return f"IMPACT ENVIRONNEMENTAL (calculé par le système) :\n{json.dumps(facts, ensure_ascii=False)}\n{rules}"
