"""
Orchestrateur du chatbot = ADAPTATEUR. Il traduit une phrase en appel au cœur, puis le résultat en réponse.
Il ne calcule rien et ne contient aucune règle agronomique. Supprimer ce dossier ne casse pas le cœur.
"""
from __future__ import annotations

from typing import Callable

from app.services.context_builder import ContextBuilder, DecisionContext

ROTATION_INTENTS = {"which_crop_to_plant", "environmental_impact"}
Explainer = Callable[[dict, dict, str], str]     # (payload, nlu, lang) -> texte ; ADAPT : llm/explanation_service.py


class ChatbotOrchestrator:
    def __init__(self, nlu: Callable[[str], dict], builder: ContextBuilder, explainer: Explainer | None = None):
        self.nlu, self.builder, self.explainer = nlu, builder, explainer

    def handle(self, db, user, text: str, *, parcelle_id=None, previous_crop=None, water_limited=False,
               n_rate=None, lang="fr") -> dict:
        u = self.nlu(text)
        base = {"intent": u["intent"], "understood": u.get("summary_fr" if lang == "fr" else "summary_en", "")}
        if u["needs_clarification"] or u["intent"] in ("unclear", "not_farming"):
            return {**base, "mode": None, "text": _t(lang, "unclear"), "figures": [], "needs_info": [], "context": {}}

        if u["intent"] in ROTATION_INTENTS:
            cands = u["crops_mentioned"]
            if parcelle_id is not None:
                ctx = self.builder.build(db, user, parcelle_id, candidates=cands, previous_crop=previous_crop,
                                         with_rotation=True, n_rate=n_rate, lang=lang)
            else:
                ctx = self.builder.build_lite(candidates=cands, previous_crop=previous_crop,
                                              water_limited=water_limited, n_rate=n_rate, lang=lang)
        elif parcelle_id is not None:
            ctx = self.builder.build(db, user, parcelle_id, lang=lang)       # eau, sol, météo... : lecture seule
        else:
            ctx = DecisionContext(lang=lang, gaps=["Aucune parcelle liée : impossible de répondre avec des données."])

        return {**base, **self._reply(ctx, u, lang)}

    def _reply(self, ctx: DecisionContext, nlu: dict, lang: str) -> dict:
        payload = ctx.payload()
        prose = None
        if self.explainer:
            try:
                prose = self.explainer(payload, nlu, lang)
            except Exception:                    # LLM indisponible : on retombe sur le texte déterministe
                prose = None
        rot = ctx.rotation or {}
        if not prose:
            prose = _fallback(rot, lang)
        # Les CHIFFRES viennent toujours du calculateur, jamais du LLM : ils sont ajoutés par le système.
        figures = ctx.impact["lines"] if ctx.impact else []
        return {"mode": ctx.mode, "text": prose, "figures": figures, "needs_info": ctx.gaps, "context": payload}


def _fallback(rot: dict, lang: str) -> str:
    top = rot.get("recommended")
    if not top:
        return _t(lang, "no_reco")
    why = next((x["reasons"] for x in rot.get("ranking", []) if x["crop"] == top), [])
    head = f"Recommandation : {top}." if lang == "fr" else f"Recommendation: {top}."
    return head + " " + " ; ".join(why)


def _t(lang: str, key: str) -> str:
    fr = {"unclear": "Je n'ai pas bien compris. Peux-tu reformuler ta question ?",
          "no_reco": "Je ne peux pas recommander une culture avec les informations actuelles."}
    en = {"unclear": "I did not understand well. Could you rephrase?",
          "no_reco": "I cannot recommend a crop with the current information."}
    return (fr if lang == "fr" else en)[key]
