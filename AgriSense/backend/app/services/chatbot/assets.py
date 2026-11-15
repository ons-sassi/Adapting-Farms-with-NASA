"""Chargement des données du chatbot (cultures reconnues + glossaire derja)."""
import json
from pathlib import Path

DATA = Path(__file__).parent / "data"


def load_crops() -> dict:
    # ADAPT (recommandé) : générer ce dict depuis le catalogue du cœur (bd/cultures.py) pour une seule source de vérité.
    return json.loads((DATA / "crops.json").read_text(encoding="utf-8"))


def load_glossary() -> dict:
    return json.loads((DATA / "glossary.json").read_text(encoding="utf-8"))
