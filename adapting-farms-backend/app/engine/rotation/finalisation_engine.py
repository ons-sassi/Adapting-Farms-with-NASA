"""Calculs économiques et de scénarios transparents, sans imputation de données."""
from __future__ import annotations
import csv, io, math
from typing import Any


def economic_score(rotations, market, area_ha):
    index={m["crop"].casefold():m for m in market}
    out=[]
    for rotation in rotations:
        crops=rotation.get("cultures", rotation.get("crops", []))
        if not crops and isinstance(rotation.get("seasons"),list): crops=rotation["seasons"]
        details=[]; total=0.0; complete=True
        for crop in crops:
            name=crop if isinstance(crop,str) else crop.get("culture",crop.get("crop",crop.get("nom","")))
            m=index.get(str(name).casefold())
            if not m or any(m.get(k) is None for k in ("yield_t_ha","price_per_t","variable_cost_per_ha")):
                complete=False; details.append({"culture":name,"marge_tnd_ha":None,"status":"DONNEES_MANQUANTES"}); continue
            margin=m["yield_t_ha"]*m["price_per_t"]-m["variable_cost_per_ha"]
            total+=margin; details.append({"culture":name,"marge_tnd_ha":round(margin,2),"marge_parcelle_tnd":round(margin*area_ha,2),"source":m.get("source"),"observed_at":m.get("observed_at"),"status":"CALCULE"})
        out.append({"rotation_id":rotation.get("id",rotation.get("nom")),"marge_rotation_tnd_ha":round(total,2) if complete else None,"marge_parcelle_tnd":round(total*area_ha,2) if complete else None,"couverture_complete":complete,"details":details})
    return out


def optimize(strategies, priorities, minimum_dimensions):
    results=[]
    for i,s in enumerate(strategies):
        dims=s.get("scores",s.get("sous_scores",{})); usable={k:float(v) for k,v in dims.items() if isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1}
        if len(usable)<minimum_dimensions: score=None
        else:
            keys=[k for k in usable if priorities.get(k,0)>0]
            den=sum(priorities[k] for k in keys)
            score=sum(usable[k]*priorities[k] for k in keys)/den if den else sum(usable.values())/len(usable)
        results.append({**s,"score_classement":round(score*100,2) if score is not None else None,"dimensions_disponibles":len(usable),"rang":None,"statut":"CLASSEMENT_POSSIBLE" if score is not None else "DONNEES_INSUFFISANTES"})
    results.sort(key=lambda x:(x["score_classement"] is None, -(x["score_classement"] or 0)))
    for rank,item in enumerate(results,1): item["rang"]=rank if item["score_classement"] is not None else None
    return results


def simulate(rotations, climate, economics):
    out=[]
    for r in rotations:
        base=r.get("scores",{})
        # Sensibilités uniquement si explicitement fournies par le modèle de culture.
        sim={}
        for dim,val in base.items():
            if not isinstance(val,(int,float)): sim[dim]=None; continue
            sens=r.get("sensibilites",{}).get(dim,{})
            delta=0.0
            for factor,variation in {**climate,**economics}.items():
                coefficient=sens.get(factor)
                if isinstance(coefficient,(int,float)): delta += coefficient*float(variation)
            sim[dim]=round(max(0,min(1,val+delta)),4)
        out.append({"rotation_id":r.get("id",r.get("nom")),"scores_base":base,"scores_simules":sim,"facteurs_appliques":{"climat":climate,"economie":economics},"limitation":"Les coefficients de sensibilité doivent être calibrés localement; sans coefficient, le score reste inchangé."})
    return out


def evidence_quality(evidence, local_validation=None):
    if not evidence: return {"niveau":"NON_EVALUABLE","score_couverture":None,"preuves":0,"avertissements":["Aucune preuve fournie"]}
    total=len(evidence); valid=sum(1 for e in evidence if e.get("source") and e.get("observed_at") and e.get("value") is not None)
    coverage=valid/total
    local=bool(local_validation and local_validation.get("validated") is True and local_validation.get("validator"))
    return {"niveau":"ELEVE" if coverage>=.85 and local else "MOYEN" if coverage>=.6 else "FAIBLE","score_couverture":round(coverage,3),"preuves":total,"preuves_documentees":valid,"validation_locale":local,"avertissements":[] if valid==total else ["Certaines preuves sont incomplètes"]}


def build_calendar(rotations):
    rows=[]
    for r in rotations:
        for crop in r.get("cultures",r.get("crops",[])):
            if isinstance(crop,str): crop={"culture":crop}
            rows.append({"rotation_id":r.get("id",r.get("nom")),"culture":crop.get("culture",crop.get("crop",crop.get("nom"))),"semis":crop.get("semis"),"recolte":crop.get("recolte"),"duree_cycle_jours":crop.get("cycle_days"),"source_calendrier":crop.get("source"),"statut":"A_VALIDER" if not crop.get("semis") or not crop.get("recolte") else "DATES_FOURNIES"})
    return rows


def parse_csv(content):
    reader=csv.DictReader(io.StringIO(content))
    if not reader.fieldnames: raise ValueError("CSV sans en-têtes")
    return [dict(row) for row in reader]
