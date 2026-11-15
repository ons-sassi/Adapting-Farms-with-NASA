"""
Decision layer (deterministic rules, no LLM).
Takes what the LLM UNDERSTOOD (candidate crops) plus a few facts (previous crop, limited water)
and ranks the candidates with transparent, editable rules (rotation_rules.json).
"""
import json
from pathlib import Path

HERE = Path(__file__).parent


def load_rules(name: str = "rotation_rules.json") -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def recommend(candidates: list, previous_crop: str | None, names: dict | None = None, water_limited: bool = False,
              rules: dict | None = None, water_mm: dict | None = None) -> dict:
    R = rules or load_rules()
    names = names or {}
    fam, w = R["families"], R["weights"]
    nm = lambda c: names.get(c, c)
    out = {"recommended": None, "ranking": [], "needs_info": [], "tie": False,
           "baseline_rotation": R["baseline_rotation"], "proposed_rotation": None}
    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        out["needs_info"].append("Aucune culture à comparer n'a été comprise dans la phrase.")
        return out
    if not previous_crop:
        out["needs_info"].append("Culture précédente inconnue : indique-la pour appliquer les règles de rotation.")

    for c in candidates:
        score, reasons = 0, []
        pf, cf = fam.get(previous_crop), fam.get(c)
        if previous_crop and cf != "perennial":
            if c == previous_crop:
                score += w["same_crop_again"]; reasons.append(f"même culture que la précédente ({nm(c)}) : risque de maladies ({w['same_crop_again']:+d})")
            elif pf == cf and cf is not None:
                score += w["same_family_again"]; reasons.append(f"même famille botanique que la précédente ({cf}) ({w['same_family_again']:+d})")
            if pf == "cereal" and cf == "legume":
                score += w["legume_after_cereal"]; reasons.append(f"légumineuse après céréale : apport d'azote ({w['legume_after_cereal']:+d})")
            if pf == "legume" and cf == "cereal":
                score += w["cereal_after_legume"]; reasons.append(f"céréale après légumineuse ({w['cereal_after_legume']:+d})")
        if water_limited:
            if water_mm and c in water_mm:
                ref = max(v["central"] for v in water_mm.values())
                bonus = round((ref - water_mm[c]["central"]) / 100 * w["water_limited_bonus_per_100mm_less"], 1)
                score += bonus; reasons.append(f"eau limitée : besoin ≈ {water_mm[c]['central']} mm ({bonus:+g})")
            else:
                reasons.append("eau limitée : pas de donnée de besoin en eau pour cette culture")
        if not reasons:
            reasons.append("aucune règle ne s'applique")
        out["ranking"].append({"crop": c, "score": score, "reasons": reasons})

    out["ranking"].sort(key=lambda x: -x["score"])
    top = out["ranking"][0]
    tied = [x for x in out["ranking"] if x["score"] == top["score"]]
    if len(tied) > 1:
        out["tie"] = True
        # transparent tie-break: prefer the crop for which we have impact figures
        have = [x for x in tied if water_mm and x["crop"] in water_mm]
        if len(have) == 1:
            top = have[0]
            top["reasons"].append("égalité de score : choisie car on dispose de chiffres d'impact pour cette culture")
        else:
            out["needs_info"].append("Plusieurs cultures sont à égalité selon les règles : une précision de l'agronome est nécessaire.")
            return out
    if not previous_crop and top["score"] == 0 and not water_limited:
        return out  # nothing distinguishes the candidates yet
    out["recommended"] = top["crop"]
    nxt = R["next_crop_after"].get(fam.get(top["crop"]))
    out["proposed_rotation"] = [top["crop"], nxt] if nxt else [top["crop"], top["crop"]]
    return out
