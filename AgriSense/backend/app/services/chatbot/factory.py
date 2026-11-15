"""Assemblage unique du chatbot : la SEULE fonction à brancher sur vos services existants."""
from dataclasses import dataclass
from typing import Callable

from app.services.chatbot.assets import load_crops, load_glossary
from app.services.chatbot.captions import make_translator
from app.services.chatbot.nlu import make_nlu
from app.services.chatbot.orchestrator import ChatbotOrchestrator
from app.services.context_builder import ContextBuilder
from app.services.impact_service import ImpactService


@dataclass
class ChatbotServices:
    orchestrator: ChatbotOrchestrator      # étape 2 + cœur
    translate: Callable[[str], str]        # étape 1 : sous-titres anglais


def build_chatbot(*, parcelles, sols, indicateurs, rotation, llm_json, llm_text, explainer=None,
                  id_map: dict | None = None) -> ChatbotServices:
    """
    parcelles / sols / indicateurs / rotation : adaptateurs sur vos services (voir context_builder.py)
    llm_json(system, user) -> dict : appel JSON de app/services/llm/groq_client.py
    llm_text(system, user) -> str  : appel texte du même client (modèle rapide conseillé pour les sous-titres)
    explainer(payload, nlu, lang) -> str : app/services/llm/explanation_service.py (optionnel)
    id_map : {id catalogue du cœur: id de impact_params.json}
    """
    impact = ImpactService(id_map=id_map)
    builder = ContextBuilder(parcelles=parcelles, sols=sols, indicateurs=indicateurs, rotation=rotation, impact=impact)
    orch = ChatbotOrchestrator(make_nlu(load_crops(), load_glossary(), llm_json), builder, explainer)
    return ChatbotServices(orch, make_translator(llm_text))
