from app.services.chatbot.nlu import make_nlu
from app.services.chatbot.orchestrator import ChatbotOrchestrator
from app.services.context_builder import ContextBuilder
from app.services.impact_service import ImpactService

CROPS = {"crops": [{"id": i, "derja": i, "fr": i} for i in ("wheat", "barley", "fava", "tomato")]}
GLOSS = {"terms": []}


def fake_llm(intent, crops):
    return lambda system, text: {"intent": intent, "crops_mentioned": crops, "summary_fr": "q", "summary_en": "q"}


class FakeParcelles:
    def get_for_user(self, db, user, pid): return {"id": pid, "surface_ha": 2.0}


class FakeLatest:
    def __init__(self, data): self.data = data
    def latest(self, db, pid): return self.data


class FakeRotation:        # imite la sortie du moteur complet : liste classée avec 'sequence'
    def recommend(self, db, pid, candidates, previous_crop):
        return {"recommended": "fava", "rotations": [{"sequence": ["fava", "wheat"], "score": 0.82},
                                                    {"sequence": ["wheat", "wheat"], "score": 0.40}]}


def orch(intent="which_crop_to_plant", crops=("fava", "wheat", "barley"), explainer=None, with_core=True):
    builder = ContextBuilder(parcelles=FakeParcelles(), sols=FakeLatest({"ph": 7.8}), indicateurs=FakeLatest(None),
                             rotation=FakeRotation(), impact=ImpactService())
    return ChatbotOrchestrator(make_nlu(CROPS, GLOSS, fake_llm(intent, list(crops))), builder, explainer)


def test_impact_is_computed_by_core_without_chatbot():
    s = ImpactService().evaluate(["fava", "wheat"], hectares=1.0)
    assert s["available"] and s["water_saved_litres"]["central"] > 0 and s["nitrogen_saved_kg"]["central"] == 130  # 100 (fève sans N) + 30 (crédit sur le blé suivant)
    assert s["n_rate_is_example"] is True


def test_unknown_crop_is_reported_not_invented():
    s = ImpactService().evaluate(["tomato", "wheat"])
    assert s["available"] is False and s["missing_data"] == ["tomato"]


def test_id_map_translates_core_ids():
    s = ImpactService(id_map={"CULT_12": "fava", "CULT_7": "wheat"}).evaluate(["CULT_12", "CULT_7"])
    assert s["available"]


def test_core_pipeline_enriches_every_ranked_rotation_with_impact():
    ctx = orch().builder.build(None, None, 1, with_rotation=True)
    ranked = ctx.rotation["rotations"]
    assert ranked[0]["impact"]["available"] and ranked[1]["impact"]["water_saved_litres"]["central"] == 0
    assert ctx.impact is ranked[0]["impact"]
    assert "indicateurs indisponible" in ctx.gaps and ctx.impact["hectares"] == 2.0


def test_impact_can_be_switched_off():
    b = orch().builder; b.impact_enabled = False
    assert b.build(None, None, 1, with_rotation=True).impact is None


def test_chatbot_core_mode_figures_come_from_calculator_not_llm():
    r = orch(explainer=lambda payload, nlu, lang: "Je conseille la fève.").handle(None, None, "x", parcelle_id=1)
    assert r["mode"] == "core" and r["text"] == "Je conseille la fève."
    assert any("CO₂e" in l for l in r["figures"])


def test_chatbot_falls_back_when_llm_fails():
    def boom(*a): raise RuntimeError("groq down")
    r = orch(explainer=boom).handle(None, None, "x", parcelle_id=1)
    assert r["figures"] and r["text"]


def test_lite_mode_without_parcelle_uses_rules_and_flags_it():
    r = orch().handle(None, None, "x", previous_crop="wheat")
    assert r["mode"] == "lite" and "fava" in r["text"] and r["figures"]
    assert any("Pas de parcelle" in g for g in r["needs_info"])


def test_non_rotation_intent_does_not_run_rotation_or_impact():
    r = orch(intent="irrigation").handle(None, None, "x", parcelle_id=1)
    assert r["figures"] == [] and "rotation" not in r["context"]


def test_unclear_question_asks_to_rephrase():
    assert "reformuler" in orch(intent="unclear").handle(None, None, "x")["text"]
