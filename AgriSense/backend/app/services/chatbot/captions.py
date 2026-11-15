"""
Étape 1 du chatbot : sous-titrage direct. La reconnaissance vocale tourne dans le NAVIGATEUR (Web Speech API, Chrome/Edge) ;
ce module ne fait que traduire chaque phrase derja en anglais pour les sous-titres (repris de subtitles.py).
"""
from typing import Callable

SYSTEM_ONE = (
    "Translate this Tunisian Arabic (Derja) text into simple, natural English. It may be an unfinished sentence. "
    "Reply with the English translation only: no quotes, no notes, no advice."
)


def make_translator(llm_text: Callable[[str, str], str]) -> Callable[[str], str]:
    """llm_text(system_prompt, user_text) -> texte brut (client Groq du cœur, de préférence un modèle rapide)."""
    def translate(text: str) -> str:
        text = (text or "").strip()[:500]
        return llm_text(SYSTEM_ONE, text).strip() if text else ""
    return translate
