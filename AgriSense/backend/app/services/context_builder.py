"""
Constructeur du CONTEXTE DE DÉCISION : un seul objet, assemblé par le cœur, consommé par
l'explication Groq, par le chatbot et par l'API. L'impact y est ajouté comme enrichissement.
Les « ports » ci-dessous sont à brancher sur vos services réels (# ADAPT).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ParcellePort(Protocol):
    def get_for_user(self, db, user, parcelle_id): ...   # ADAPT parcelle_service ; doit refuser si l'utilisateur n'est pas propriétaire


class LatestPort(Protocol):
    def latest(self, db, parcelle_id): ...               # ADAPT sol_service / indicateur_service


class RotationPort(Protocol):
    def recommend(self, db, parcelle_id, candidates, previous_crop): ...  # ADAPT app/engine/rotation (pipeline complet)


@dataclass
class DecisionContext:
    lang: str = "fr"
    mode: str = "core"                     # "core" = moteur complet ; "lite" = règles simplifiées (sans parcelle)
    parcelle: dict | None = None
    sol: dict | None = None
    indicateurs: dict | None = None
    rotation: dict | None = None
    impact: dict | None = None
    gaps: list = field(default_factory=list)   # données manquantes, jamais comblées par une invention

    def payload(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, [], {})}


class ContextBuilder:
    def __init__(self, *, parcelles: ParcellePort | None = None, sols: LatestPort | None = None,
                 indicateurs: LatestPort | None = None, rotation: RotationPort | None = None,
                 impact=None, impact_enabled: bool = True):
        self.parcelles, self.sols, self.indicateurs = parcelles, sols, indicateurs
        self.rotation, self.impact, self.impact_enabled = rotation, impact, impact_enabled

    # ---------------------------------------------------------------- mode cœur (parcelle connue)
    def build(self, db, user, parcelle_id, *, candidates=(), previous_crop=None, with_rotation=False,
              n_rate=None, lang="fr") -> DecisionContext:
        ctx = DecisionContext(lang=lang)
        ctx.parcelle = self.parcelles.get_for_user(db, user, parcelle_id)
        for name, port in (("sol", self.sols), ("indicateurs", self.indicateurs)):
            data = port.latest(db, parcelle_id) if port else None
            setattr(ctx, name, data)
            if not data:
                ctx.gaps.append(f"{name} indisponible")
        if with_rotation:
            ctx.rotation = self.rotation.recommend(db, parcelle_id, list(candidates), previous_crop)
            self._enrich_impact(ctx, n_rate)
        return ctx

    # ---------------------------------------------------------------- mode lite (sans parcelle)
    def build_lite(self, *, candidates, previous_crop=None, water_limited=False, hectares=1.0, n_rate=None,
                   lang="fr") -> DecisionContext:
        from app.engine.rotation import lite_rules
        water = self.impact.params["water_requirement_mm"] if self.impact else None
        ctx = DecisionContext(lang=lang, mode="lite")
        ctx.rotation = lite_rules.recommend(list(candidates), previous_crop, water_limited=water_limited, water_mm=water)
        ctx.gaps += ctx.rotation.get("needs_info", [])
        ctx.gaps.append("Pas de parcelle liée : règles simplifiées, sans sol ni climat.")
        self._enrich_impact(ctx, n_rate, hectares_default=hectares)
        return ctx

    # ---------------------------------------------------------------- enrichissement impact
    def _enrich_impact(self, ctx: DecisionContext, n_rate, hectares_default: float = 1.0):
        if not (self.impact_enabled and self.impact and ctx.rotation):
            return
        p = ctx.parcelle or {}
        ha = p.get("surface_ha") or p.get("superficie_ha")      # ADAPT : nom réel du champ surface
        if not ha:
            ha = hectares_default
            ctx.gaps.append(f"surface inconnue : impact calculé pour {ha:g} ha")
        kw = dict(hectares=float(ha), n_rate=n_rate, lang=ctx.lang)
        # moteur complet : liste classée de rotations (chacune avec sa 'sequence') ; mode lite : proposed_rotation
        ranked = ctx.rotation.get("rotations") or []
        if ranked:
            self.impact.enrich_ranking(ranked, **kw)
            ctx.impact = ranked[0].get("impact")
        elif ctx.rotation.get("proposed_rotation"):
            ctx.impact = self.impact.evaluate(ctx.rotation["proposed_rotation"], **kw)
        if ctx.impact and not ctx.impact["available"]:
            ctx.gaps.append("impact non chiffrable pour : " + ", ".join(ctx.impact["missing_data"]))
        if ctx.impact and ctx.impact.get("n_rate_is_example"):
            ctx.gaps.append("dose d'azote = valeur d'exemple (renseigner la dose réelle du fermier)")
