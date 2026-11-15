"""
NLU du chatbot : texte (derja) -> JSON structuré {intent, cultures, ...}.
Repris de agriculture/llm.py. Différences :
  - aucune clé / aucun client ici : l'appel LLM est INJECTÉ (on réutilise app/services/llm/groq_client.py du cœur)
  - crops et glossary sont passés en paramètres (idéalement lus depuis le catalogue bd/cultures.py)
  - nouvelle intention : environmental_impact
Le LLM COMPREND seulement ; il ne conseille pas et ne calcule rien.
"""
import json
from typing import Callable

INTENTS = [
    "which_crop_to_plant",  # que planter / quelle culture
    "irrigation",           # arrosage, eau
    "soil_condition",       # état du sol, terre sèche/humide
    "fertilizer",           # engrais, fumier
    "pest_disease",         # maladies, insectes, mauvaises herbes
    "harvest",              # récolte
    "environmental_impact", # eau / engrais / CO2 économisés (-> calculateur d'impact)
    "weather",              # pluie, température, gel
    "other_farming",        # agricole mais autre sujet
    "not_farming",          # hors sujet
    "unclear",              # incompréhensible
]



def apply_glossary(text: str, glossary: dict) -> str:
    """Remplace seulement les variantes SÛRES (les ambiguës restent au LLM)."""
    for term in glossary["terms"]:
        for v in term.get("variants_safe", []):
            text = text.replace(v, term["correct"])
    return text


def glossary_hints(glossary: dict) -> str:
    """Ambiguous mis-transcriptions get their own line; plain vocabulary is packed into one compact line."""
    lines, vocab = [], []
    for t in glossary["terms"]:
        amb = t.get("variants_ambiguous", [])
        if amb:
            lines.append(f"- '{t['correct']}' ({t['meaning']}) may be mis-transcribed as: "
                         + ", ".join(amb) + ". Pick the reading that fits a farming sentence.")
        else:
            vocab.append(f"{t['correct']} = {t['meaning']}")
    if vocab:
        lines.append("- Farming vocabulary (Derja): " + "; ".join(vocab) + ".")
    return "\n".join(lines)


def build_prompt(crops: dict, glossary: dict) -> str:
    crop_lines = "\n".join(f"- id={c['id']}: {c['derja']} ({c['fr']})" for c in crops["crops"])
    return f"""You are the language-understanding module of a farming assistant for Tunisian farmers.
The input is a Tunisian Derja sentence produced by speech recognition. It may contain transcription errors, French words, and merged or split words.

YOUR ONLY JOB: understand the sentence and extract information. Do NOT answer the question. Do NOT give advice.

Known crops (use the id when the farmer mentions one, including by a misspelled or alternative name):
{crop_lines}

Known transcription confusions and vocabulary:
{glossary_hints(glossary)}

Return ONLY one JSON object with exactly these keys:
- "intent": one of {INTENTS}
- "crops_mentioned": list of crop ids from the known crops list that the farmer mentions
- "crops_unknown": list of crop names (as written) that the farmer mentions but are NOT in the known list
- "place_term": the type of plot or place mentioned (e.g. "sania"), or null
- "time_reference": any time mention (e.g. "this year", "now", "next month"), or null
- "summary_fr": one short French sentence stating what the farmer is asking
- "summary_en": the same summary as one short English sentence
- "uncertain_words": list of words you were not confident about
- "needs_clarification": true if the sentence is too unclear to act on, else false
Do not add any other text."""


def validate(raw: dict, crops: dict) -> dict:
    """Ne fait pas confiance au LLM : on vérifie et on corrige la structure."""
    valid_ids = {c["id"] for c in crops["crops"]}
    mentioned = [c for c in raw.get("crops_mentioned", []) if c in valid_ids]
    leaked = [c for c in raw.get("crops_mentioned", []) if c not in valid_ids]
    unknown = list(raw.get("crops_unknown", [])) + leaked
    intent = raw.get("intent")
    return {
        "intent": intent if intent in INTENTS else "unclear",
        "crops_mentioned": list(dict.fromkeys(mentioned)),
        "crops_unknown": list(dict.fromkeys(unknown)),
        "place_term": raw.get("place_term"),
        "time_reference": raw.get("time_reference"),
        "summary_fr": str(raw.get("summary_fr", "")),
        "summary_en": str(raw.get("summary_en", "")),
        "uncertain_words": list(raw.get("uncertain_words", [])),
        "needs_clarification": bool(raw.get("needs_clarification", False)) or intent not in INTENTS,
    }



def make_nlu(crops: dict, glossary: dict, llm_json: Callable[[str, str], dict]) -> Callable[[str], dict]:
    """Retourne une fonction text -> dict validé. llm_json(system_prompt, user_text) -> dict (JSON)."""
    system_prompt = build_prompt(crops, glossary)

    def understand(transcript: str) -> dict:
        cleaned = apply_glossary(transcript, glossary)
        result = validate(llm_json(system_prompt, cleaned), crops)
        result["cleaned_text"] = cleaned
        return result

    return understand
