"""Branchement du module chatbot (adaptateurs) sur les services réels du backend.

C'est ici que sont remplis les « # ADAPT » du module : parcelles, sol, indicateurs,
moteur de rotation, client Groq et explication. Le module chatbot lui-même n'est pas modifié.
"""
from __future__ import annotations

import json
from functools import lru_cache

from sqlalchemy import select

from app.core.config import settings
from app.services.chatbot.factory import ChatbotServices, build_chatbot
from app.services.impact_service import ImpactService

# Identifiants du chatbot (crops.json) -> identifiants du catalogue de l'interface (frontend_catalog)
CHAT_TO_CATALOG = {
    "wheat": "ble-dur", "barley": "orge", "fava": "feve-feverole", "chickpea": "pois-chiche",
    "tomato": "tomate", "pepper": "piment-poivron", "watermelon": "pasteque", "melon": "melon",
    "cabbage": "chou-pomme", "squash": "courge-potiron", "cowpea": "haricot-sec", "eggplant": "aubergine",
    "broccoli": "brocoli", "carrot": "carotte", "artichoke": "artichaut", "olive": "olivier",
}
CATALOG_TO_CHAT = {v: k for k, v in CHAT_TO_CATALOG.items()}
CATALOG_TO_CHAT["ble-tendre"] = "wheat"
CATALOG_TO_CHAT["lentille"] = "lentil"
# Cultures comparées quand le fermier demande « que planter ? » sans en citer.
DEFAULT_CANDIDATES = ["ble-dur", "orge", "feve-feverole", "pois-chiche", "lentille", "sorgho"]
DEFAULT_PRIORITIES = {"water": 3, "yield": 3, "soil": 3, "profit": 3, "resilience": 3, "pests": 3, "sustainability": 3}


# --------------------------------------------------------------------------- #
# Adaptateurs (ports de context_builder.py)
# --------------------------------------------------------------------------- #
class ParcelleAdapter:
    def get_for_user(self, db, user, parcelle_id):
        from app.api.v1.frontend_bridge import _latest_ph, _owned_parcel, parcel_to_front

        parcel = _owned_parcel(db, str(parcelle_id), user)        # 404 si la parcelle n'est pas à lui
        data = parcel_to_front(parcel, _latest_ph(db, parcel.id))
        data.pop("geometry", None)
        data["surface_ha"] = parcel.area_ha
        return data


class SolAdapter:
    def latest(self, db, parcelle_id):
        from app.models.sol import SoilAnalysis
        from app.services import parcel_environment
        from app.models.parcelle import Parcelle

        row = db.scalar(select(SoilAnalysis).where(SoilAnalysis.parcelle_id == parcelle_id)
                        .order_by(SoilAnalysis.id.desc()))
        if row is not None:
            keys = ("ph", "organic_matter_percent", "texture", "nitrogen_mg_kg", "phosphorus_mg_kg",
                    "potassium_mg_kg", "salinity_ds_m", "limestone_percent", "cec_cmol_kg", "source")
            return {k: getattr(row, k) for k in keys if getattr(row, k) is not None}
        parcel = db.get(Parcelle, parcelle_id)
        env = parcel_environment.get_for_parcel(db, parcel) if parcel else None
        return (env or {}).get("soil")


class IndicateursAdapter:
    def latest(self, db, parcelle_id):
        from app.models.parcelle import Parcelle
        from app.services import parcel_environment

        parcel = db.get(Parcelle, parcelle_id)
        env = parcel_environment.get_for_parcel(db, parcel) if parcel else None
        if not env:
            return None
        climate = env.get("climate") or {}
        out = {
            "climat": {k: climate.get(k) for k in ("source", "year", "annual_rain_mm", "annual_et0_mm", "tmean_c")} if climate else None,
            "humidite_sol": env.get("soil_moisture"),
            "pluie_12_mois": {k: v for k, v in (env.get("precipitation") or {}).items() if k != "months"} or None,
            "vegetation": env.get("vegetation"),
        }
        return {k: v for k, v in out.items() if v} or None


class RotationAdapter:
    def recommend(self, db, parcelle_id, candidates, previous_crop):
        from app.api.v1.frontend_bridge import _latest_ph, parcel_to_front
        from app.models.parcelle import Parcelle
        from app.services import frontend_catalog as catalog, parcel_environment
        from app.services.frontend_analysis_service import run_analysis

        parcel = db.get(Parcelle, parcelle_id)
        front = parcel_to_front(parcel, _latest_ph(db, parcel.id))
        if previous_crop:
            prev = catalog.get_crop(CHAT_TO_CATALOG.get(previous_crop, previous_crop))
            front["crop"] = prev["name"] if prev else previous_crop
        ids = [CHAT_TO_CATALOG.get(c, c) for c in candidates]
        ids = [i for i in dict.fromkeys(ids) if catalog.get_crop(i) and catalog.get_crop(i)["eligible"]]
        note = None
        if len(ids) < 2:
            note = "Moins de 2 cultures éligibles citées : comparaison élargie aux cultures courantes."
            ids = list(dict.fromkeys(ids + DEFAULT_CANDIDATES))
        try:
            env = parcel_environment.get_for_parcel(db, parcel)
        except Exception:  # noqa: BLE001
            env = None
        result = run_analysis({"crops": ids, "priorities": DEFAULT_PRIORITIES, "horizon": 4, "constraints": {}},
                              front, front["ph"], environment=env)
        name = lambda cid: (catalog.get_crop(cid) or {}).get("name", cid)  # noqa: E731
        rotations = []
        for r in result["rotations"]:
            rotations.append({
                "name": r["name"], "score": r["score"],
                "crop": name(r["years"][0]),
                "sequence": [CATALOG_TO_CHAT.get(c, c) for c in r["years"]],
                "sequence_names": [name(c) for c in r["years"]],
                "reasons": (r["pros"] + r["cons"])[:4], "risks": r["risks"][:3],
                "calendar": r.get("calendar"),
            })
        rotations.sort(key=lambda r: -r["score"])
        out = {
            "recommended": rotations[0]["crop"] if rotations else None,
            "ranking": rotations, "rotations": rotations,
            "excluded": result.get("excludedCrops"), "data_sources": result.get("dataSources"),
            "needs_info": [note] if note else [],
        }
        if not rotations:
            out["needs_info"].append(result.get("notice") or "Aucune rotation possible avec ces cultures.")
        return out


# --------------------------------------------------------------------------- #
# Client Groq synchrone (le module chatbot appelle des fonctions synchrones)
# --------------------------------------------------------------------------- #
def _groq():
    from groq import Groq

    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY non défini dans backend/.env")
    return Groq(api_key=settings.groq_api_key, timeout=settings.groq_timeout_seconds, max_retries=1)


def llm_json(system: str, user: str) -> dict:
    r = _groq().chat.completions.create(
        model=settings.groq_model, temperature=0, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return json.loads(r.choices[0].message.content or "{}")


def llm_text(system: str, user: str) -> str:
    r = _groq().chat.completions.create(
        model=settings.groq_caption_model or settings.groq_model, temperature=0, max_completion_tokens=200,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return r.choices[0].message.content or ""


EXPLAIN_PROMPT = """Tu es l'assistant agricole d'AgriSense pour des agriculteurs tunisiens.
Réponds à la question de l'agriculteur en {lang_name}, simplement, en 3 à 6 phrases.
Règles strictes :
- Utilise UNIQUEMENT les données du CONTEXTE ci-dessous (parcelle, sol, indicateurs, rotation, impact).
- N'invente aucun chiffre. Les chiffres d'impact sont affichés à part : ne les recopie pas, résume l'idée.
- Si une donnée manque (voir "gaps"), dis-le clairement et ce qu'il faudrait fournir.
- Pas de markdown, pas de liste à puces (la réponse peut être lue à voix haute)."""


def explainer(payload: dict, nlu: dict, lang: str) -> str:
    impact = payload.get("impact")
    ctx = {k: v for k, v in payload.items() if k != "impact"}
    blocks = [f"CONTEXTE :\n{json.dumps(ctx, ensure_ascii=False, default=str)[:12000]}"]
    if impact:
        blocks.append(ImpactService.prompt_block(impact, lang))
    question = nlu.get("summary_fr" if lang == "fr" else "summary_en") or nlu.get("cleaned_text", "")
    r = _groq().chat.completions.create(
        model=settings.groq_model, temperature=0.2, max_completion_tokens=600,
        messages=[{"role": "system", "content": EXPLAIN_PROMPT.format(lang_name="français" if lang == "fr" else "anglais")},
                  {"role": "user", "content": "\n\n".join(blocks) + f"\n\nQUESTION : {question}"}])
    return (r.choices[0].message.content or "").strip()


@lru_cache(maxsize=1)
def get_services() -> ChatbotServices:
    from app.services.chatbot.assets import load_crops

    services = build_chatbot(
        parcelles=ParcelleAdapter(), sols=SolAdapter(), indicateurs=IndicateursAdapter(), rotation=RotationAdapter(),
        llm_json=llm_json, llm_text=llm_text, explainer=explainer,
        id_map={"ble-dur": "wheat", "ble-tendre": "wheat", "feve-feverole": "fava"},
    )
    # Noms français dans les chiffres d'impact (« fève → blé » plutôt que « fava → wheat »)
    services.orchestrator.builder.impact.names = {c["id"]: c["fr"] for c in load_crops()["crops"]}
    return services
