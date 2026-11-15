"""
Climate impact calculator (deterministic, no LLM).
Compares a PROPOSED rotation with a CLASSIC one (wheat -> wheat) over the same seasons and returns:
  - crop water requirement saved (litres)
  - nitrogen fertiliser avoided (kg N)
  - greenhouse-gas emissions avoided (kg CO2e), from the N2O of applied nitrogen (sourced)
    and, separately, from fertiliser manufacture (estimate)
All parameters, ranges and sources live in impact_params.json. A crop without parameters is reported as
"missing data" instead of being guessed.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent


def load_params(name: str = "impact_params.json") -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def _rng(d: dict) -> tuple:
    c = d["central"]
    return d.get("low", c), c, d.get("high", c)


def _scale(t: tuple, k: float) -> dict:
    return {"low": t[0] * k, "central": t[1] * k, "high": t[2] * k}


def compute_impact(proposed: list, baseline: list, hectares: float = 1.0, n_rate=None,
                   params: dict | None = None, names: dict | None = None) -> dict:
    P = params or load_params()
    names = names or {}
    W, N, E = P["water_requirement_mm"], P["nitrogen"], P["emissions"]
    cereals, legumes = set(P["roles"]["cereals"]), set(P["roles"]["n_credit_legumes"])
    missing = sorted({c for c in proposed + baseline if c not in W or (c not in cereals and c not in legumes)})
    out = {"ok": not missing, "missing_data": missing, "proposed": proposed, "baseline": baseline,
           "hectares": hectares, "names": names, "warnings": [], "assumptions": [], "sources": {}}
    if missing or len(proposed) != len(baseline):
        return out

    mm = P["units"]
    # ---- water: only seasons where the crops differ count (identical seasons cancel out) ----
    lo = ce = hi = 0.0
    for p, b in zip(proposed, baseline):
        if p == b:
            continue
        lo += W[b]["low"] - W[p]["high"]
        ce += W[b]["central"] - W[p]["central"]
        hi += W[b]["high"] - W[p]["low"]
    water_total = lambda seq: sum(W[c]["central"] for c in seq)           # mm, central
    out["water"] = {
        "baseline_m3": water_total(baseline) * mm["m3_per_mm_per_ha"] * hectares,
        "proposed_m3": water_total(proposed) * mm["m3_per_mm_per_ha"] * hectares,
        "saved_litres": _scale((lo, ce, hi), mm["litres_per_mm_per_ha"] * hectares),
    }

    # ---- nitrogen ----
    rate = n_rate if n_rate is not None else N["reference_cereal_n_rate_kg_ha"]["central"]
    legume_rate = N["legume_own_n_rate_kg_ha"]["central"]
    credit = _rng(N["n_credit_next_cereal_kg_ha"])

    def n_applied(seq, credit_value):
        total = 0.0
        for i, c in enumerate(seq):
            if c in cereals:
                dose = rate
                if i > 0 and seq[i - 1] in legumes:
                    dose = max(0.0, dose - credit_value)
                total += dose
            else:
                total += legume_rate
        return total

    base_n = n_applied(baseline, 0.0)
    prop_n = [n_applied(proposed, credit[k]) for k in range(3)]               # low credit, central, high credit
    saved_n = (base_n - prop_n[0], base_n - prop_n[1], base_n - prop_n[2])
    credit_used = sum(1 for i, c in enumerate(proposed) if i > 0 and c in cereals and proposed[i - 1] in legumes)
    out["nitrogen"] = {
        "reference_rate_kg_ha": rate, "baseline_kg": base_n * hectares, "proposed_kg": prop_n[1] * hectares,
        "saved_kg": _scale(saved_n, hectares), "credit_part_kg_central": credit[1] * credit_used * hectares,
        "rate_is_example": n_rate is None,
    }

    # ---- emissions from the nitrogen not applied ----
    ef1, gwp, conv = _rng(E["n2o_ef1_direct"]), E["n2o_gwp100"]["central"], E["n2o_n_to_n2o"]["central"]
    field = tuple(x * conv * gwp for x in ef1)                                # kg CO2e per kg N (field N2O)
    prod = _rng(E["production_transport_kgco2e_per_kg_n"])
    co2_field = (saved_n[0] * field[0], saved_n[1] * field[1], saved_n[2] * field[2])
    co2_total = tuple(co2_field[k] + saved_n[k] * prod[k] for k in range(3))
    out["co2e"] = {
        "field_n2o_kg": _scale(co2_field, hectares),
        "with_production_kg": _scale(co2_total, hectares),
        "factor_field_kg_per_kg_n": field[1], "factor_production_kg_per_kg_n": prod[1],
        "baseline_field_kg": base_n * field[1] * hectares, "proposed_field_kg": prop_n[1] * field[1] * hectares,
    }

    for c in sorted(set(proposed + baseline)):
        out["sources"][f"water: {c}"] = W[c]["source"] + f" [{W[c]['confidence']}]"
    out["sources"]["nitrogen credit"] = N["n_credit_next_cereal_kg_ha"]["source"]
    out["sources"]["N2O factor"] = E["n2o_ef1_direct"]["source"] + " GWP: " + E["n2o_gwp100"]["source"]
    out["sources"]["fertiliser production (estimate)"] = E["production_transport_kgco2e_per_kg_n"]["source"]
    out["assumptions"] = [
        f"Dose d'azote sur céréale : {rate:g} kg N/ha" + (" (valeur d'EXEMPLE : remplace-la)" if n_rate is None else ""),
        "Le besoin en eau est celui de la culture (pluie + irrigation), pas forcément de l'eau d'irrigation économisée.",
        "Le crédit azote de la fève profite à la céréale de la saison suivante, pas à la saison en cours.",
        "Seul le N2O direct du sol est compté dans le chiffre principal (sourcé) ; la fabrication de l'engrais est une estimation.",
        "Aucun stockage de carbone dans le sol n'est compté (trop variable pour être annoncé).",
    ]
    if W["fava"]["confidence"] != "sourced" and "fava" in proposed + baseline:
        out["warnings"].append("Besoin en eau de la fève : valeurs d'Egypte, indicatives pour la Tunisie.")
    return out


# ---------------------------------------------------------------- messages
def _num(x: float, nd: int = 0) -> str:
    return f"{x:,.{nd}f}".replace(",", " ")


def _litres(l: float, lang: str) -> str:
    a = abs(l)
    if a >= 1e6:
        v = l / 1e6
        return f"{v:.2f} million{'s' if lang == 'fr' and abs(v) >= 2 else ''} {'de litres' if lang == 'fr' else 'litres'}".replace(".", "," if lang == "fr" else ".")
    return f"{_num(l)} {'litres' if lang == 'en' else 'litres'}"


def _label(seq: list, names: dict) -> str:
    return " → ".join(names.get(c, c) for c in seq)


def format_message(r: dict, lang: str = "fr") -> list:
    """Short bullet lines for the chatbot. Numbers come from the calculator, never from an LLM."""
    names = r.get("names", {})
    if not r["ok"]:
        miss = ", ".join(names.get(c, c) for c in r["missing_data"]) or "-"
        return [f"Pas de chiffres d'impact pour : {miss} (paramètres absents de impact_params.json)."
                if lang == "fr" else f"No impact figures for: {miss} (parameters missing in impact_params.json)."]
    h = r["hectares"]
    w, n, c = r["water"]["saved_litres"], r["nitrogen"]["saved_kg"], r["co2e"]
    cf, ct = c["field_n2o_kg"], c["with_production_kg"]
    head = f"{_label(r['proposed'], names)}  vs  {_label(r['baseline'], names)}  ({h:g} ha)"
    if lang == "fr":
        return [
            head,
            f"💧 Eau : environ {_litres(w['central'], 'fr')} de moins en besoin en eau de la culture (fourchette {_litres(w['low'], 'fr')} à {_litres(w['high'], 'fr')}).",
            f"🌱 Azote : environ {_num(n['central'])} kg N d'engrais en moins sur deux saisons (fourchette {_num(n['low'])} à {_num(n['high'])}), dont ~{_num(r['nitrogen']['credit_part_kg_central'])} kg grâce à la légumineuse qui précède la céréale.",
            f"🌍 Climat : environ {_num(cf['central'])} kg CO₂e évités (N₂O du sol, fourchette {_num(cf['low'])} à {_num(cf['high'])}) ; environ {_num(ct['central'])} kg en comptant la fabrication de l'engrais (estimation).",
            "Chiffres indicatifs, à valider par l'agronome.",
        ]
    return [
        head,
        f"💧 Water: about {_litres(w['central'], 'en')} less crop water requirement (range {_litres(w['low'], 'en')} to {_litres(w['high'], 'en')}).",
        f"🌱 Nitrogen: about {_num(n['central'])} kg N less fertiliser over two seasons (range {_num(n['low'])} to {_num(n['high'])}), of which ~{_num(r['nitrogen']['credit_part_kg_central'])} kg thanks to the legume before the cereal.",
        f"🌍 Climate: about {_num(cf['central'])} kg CO₂e avoided (soil N₂O, range {_num(cf['low'])} to {_num(cf['high'])}); about {_num(ct['central'])} kg including fertiliser manufacture (estimate).",
        "Indicative figures, to be validated by an agronomist.",
    ]


# ------------------------------------------------------------------- chart
def make_figure(r: dict):
    """Plotly bars: classic rotation vs proposed rotation (3 panels)."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    names = r.get("names", {})
    lab_b, lab_p = f"Classique ({_label(r['baseline'], names)})", f"Proposée ({_label(r['proposed'], names)})"
    panels = [
        ("Besoin en eau (m³)", r["water"]["baseline_m3"], r["water"]["proposed_m3"]),
        ("Azote apporté (kg N)", r["nitrogen"]["baseline_kg"], r["nitrogen"]["proposed_kg"]),
        ("Émissions N₂O du sol (kg CO₂e)", r["co2e"]["baseline_field_kg"], r["co2e"]["proposed_field_kg"]),
    ]
    fig = make_subplots(rows=1, cols=3, subplot_titles=[p[0] for p in panels])
    for i, (_, b, p) in enumerate(panels, start=1):
        fig.add_trace(go.Bar(x=[lab_b], y=[b], marker_color="#9e9e9e", name=lab_b, showlegend=(i == 1),
                             text=[_num(b)], textposition="outside"), row=1, col=i)
        fig.add_trace(go.Bar(x=[lab_p], y=[p], marker_color="#2e7d32", name=lab_p, showlegend=(i == 1),
                             text=[_num(p)], textposition="outside"), row=1, col=i)
    fig.update_xaxes(showticklabels=False)
    fig.update_layout(height=380, margin=dict(t=60, b=20, l=10, r=10), legend=dict(orientation="h", y=-0.05),
                      title_text="Rotation proposée vs rotation classique (valeurs centrales, indicatives)")
    return fig
