from app.services.chatbot.assets import load_crops, load_glossary
from app.services.chatbot.nlu import INTENTS, make_nlu


def test_assets_load_and_nlu_validates_against_real_crop_list():
    crops, gloss = load_crops(), load_glossary()
    ids = {c["id"] for c in crops["crops"]}
    assert {"wheat", "fava", "barley"} <= ids and gloss["terms"]
    # le LLM invente une culture hors catalogue : elle est déplacée dans crops_unknown, jamais utilisée
    nlu = make_nlu(crops, gloss, lambda s, t: {"intent": "environmental_impact",
                                                "crops_mentioned": ["fava", "dragonfruit"]})
    r = nlu("x")
    assert r["crops_mentioned"] == ["fava"] and r["crops_unknown"] == ["dragonfruit"]
    assert "environmental_impact" in INTENTS


def test_unknown_intent_becomes_unclear():
    nlu = make_nlu(load_crops(), load_glossary(), lambda s, t: {"intent": "hack"})
    assert nlu("x")["intent"] == "unclear" and nlu("x")["needs_clarification"]
