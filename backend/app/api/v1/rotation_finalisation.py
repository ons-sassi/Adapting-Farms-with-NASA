"""Endpoints complémentaires : marché, optimisation, simulations, fiabilité, sorties et données."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user, get_db
from app.models.parcelle import Parcelle
from app.schemas.rotation_finalisation import EconomicRequest, OptimizeRequest, SimulationRequest, ReliabilityRequest, FeedbackRequest, ImportRequest
from app.engine.rotation.finalisation_engine import economic_score, optimize, simulate, evidence_quality, build_calendar, parse_csv
import json, uuid, html, io

router=APIRouter(prefix="/rotation", tags=["Rotation - Finalisation"])

def owned(db, user, pid):
    p=db.query(Parcelle).filter(Parcelle.id==pid,Parcelle.farmer_id==user.id).first()
    if not p: raise HTTPException(404,"Parcelle introuvable")
    return p

@router.post("/parcelles/{parcelle_id}/moteur-decision")
def decision(parcelle_id:int,payload:EconomicRequest,db:Session=Depends(get_db),user=Depends(get_current_user)):
    owned(db,user,parcelle_id)
    econ=economic_score([x for x in payload.rotations], [m.model_dump() for m in payload.market],payload.area_ha)
    result=[]
    for r,e in zip(payload.rotations,econ):
        scores=r.get("scores",r.get("sous_scores",{})).copy()
        if e["marge_rotation_tnd_ha"] is not None: scores["economique"]=max(0,min(1,(e["marge_rotation_tnd_ha"]+5000)/10000))
        else: scores["economique"]=None
        result.append({"rotation_id":e["rotation_id"],"marge":e,"scores":scores,"score_global":None,"notice":"La normalisation économique ci-dessus est une convention technique provisoire à valider; le score global nécessite des poids agronomiques validés et une couverture suffisante."})
    return {"parcelle_id":parcelle_id,"resultats":result}

@router.post("/parcelles/{parcelle_id}/optimiser")
def optimisation(parcelle_id:int,payload:OptimizeRequest,db:Session=Depends(get_db),user=Depends(get_current_user)):
    owned(db,user,parcelle_id)
    return {"parcelle_id":parcelle_id,"strategies_classees":optimize(payload.strategies,payload.priorities,payload.minimum_dimensions),"calendrier":build_calendar(payload.strategies),"notice":"Le moteur classe au plus trois stratégies candidates fournies; il ne crée pas de nouvelles rotations ni de dates agronomiques sans fenêtres validées."}

@router.post("/parcelles/{parcelle_id}/simuler")
def simulations(parcelle_id:int,payload:SimulationRequest,db:Session=Depends(get_db),user=Depends(get_current_user)):
    owned(db,user,parcelle_id)
    return {"parcelle_id":parcelle_id,"scenarios":simulate(payload.rotations,payload.climate,payload.economics)}

@router.post("/parcelles/{parcelle_id}/fiabilite")
def fiabilite(parcelle_id:int,payload:ReliabilityRequest,db:Session=Depends(get_db),user=Depends(get_current_user)):
    owned(db,user,parcelle_id)
    return {"parcelle_id":parcelle_id,**evidence_quality(payload.evidence,payload.local_validation),"snapshot_id":payload.snapshot_id}

@router.post("/parcelles/{parcelle_id}/calendrier")
def calendrier(parcelle_id:int,payload:OptimizeRequest,db:Session=Depends(get_db),user=Depends(get_current_user)):
    owned(db,user,parcelle_id)
    return {"parcelle_id":parcelle_id,"calendrier":build_calendar(payload.strategies),"notice":"Les dates manquantes ne sont pas inventées."}

@router.post("/parcelles/{parcelle_id}/rapport")
def rapport(parcelle_id:int,payload:dict,db:Session=Depends(get_db),user=Depends(get_current_user)):
    owned(db,user,parcelle_id)
    body=html.escape(json.dumps(payload,ensure_ascii=False,indent=2))
    page=f"<!doctype html><html lang='fr'><meta charset='utf-8'><title>Rapport agricole</title><body><h1>Rapport de rotation – Parcelle {parcelle_id}</h1><pre>{body}</pre></body></html>"
    return Response(page,media_type="text/html",headers={"Content-Disposition":f"attachment; filename=rapport_rotation_{parcelle_id}.html"})

@router.post("/parcelles/{parcelle_id}/rapport/pdf")
def rapport_pdf(parcelle_id:int,payload:dict,db:Session=Depends(get_db),user=Depends(get_current_user)):
    owned(db,user,parcelle_id)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        raise HTTPException(503,"Installer reportlab : pip install reportlab")
    buffer=io.BytesIO(); pdf=canvas.Canvas(buffer,pagesize=A4)
    width,height=A4; y=height-48
    pdf.setTitle(f"Rapport rotation parcelle {parcelle_id}")
    pdf.setFont("Helvetica-Bold",15); pdf.drawString(42,y,f"Rapport de rotation - Parcelle {parcelle_id}"); y-=30
    pdf.setFont("Helvetica",9)
    content=json.dumps(payload,ensure_ascii=True,indent=2).splitlines()
    for line in content:
        if y<48: pdf.showPage(); y=height-48; pdf.setFont("Helvetica",9)
        pdf.drawString(42,y,line[:110]); y-=13
    pdf.save(); buffer.seek(0)
    return Response(buffer.getvalue(),media_type="application/pdf",headers={"Content-Disposition":f"attachment; filename=rapport_rotation_{parcelle_id}.pdf"})

@router.post("/parcelles/{parcelle_id}/retours-conseiller")
def feedback(parcelle_id:int,payload:FeedbackRequest,db:Session=Depends(get_db),user=Depends(get_current_user)):
    owned(db,user,parcelle_id)
    try:
        db.execute(text("INSERT INTO rotation_advisor_feedback (parcel_id,user_id,recommendation_id,rating,comment,accepted,adjustments_json) VALUES (:p,:u,:r,:rating,:comment,:accepted,:adjustments)"),{"p":parcelle_id,"u":user.id,"r":payload.recommendation_id,"rating":payload.rating,"comment":payload.comment,"accepted":payload.accepted,"adjustments":json.dumps(payload.local_adjustments,ensure_ascii=False)})
        db.commit()
    except Exception as exc:
        db.rollback(); raise HTTPException(503,"Table de retours non installée : appliquer la migration 006") from exc
    return {"saved":True,"recommendation_id":payload.recommendation_id}

@router.post("/marche/prix")
def enregistrer_prix_marche(payload:dict,db:Session=Depends(get_db),user=Depends(get_current_user)):
    required=("crop","region","price_per_t","currency","source","observed_at")
    missing=[k for k in required if payload.get(k) is None]
    if missing: raise HTTPException(422,{"champs_manquants":missing})
    try:
        db.execute(text("INSERT INTO rotation_market_prices (user_id,crop,region,price_per_t,currency,source,observed_at,metadata_json) VALUES (:u,:crop,:region,:price,:currency,:source,:date,:meta)"),{"u":user.id,"crop":payload["crop"],"region":payload["region"],"price":float(payload["price_per_t"]),"currency":payload["currency"],"source":payload["source"],"date":payload["observed_at"],"meta":json.dumps(payload.get("metadata",{}),ensure_ascii=False)})
        db.commit()
    except Exception as exc:
        db.rollback(); raise HTTPException(503,"Table marché absente : appliquer la migration 006") from exc
    return {"saved":True,"message":"Observation de marché enregistrée avec sa provenance."}

@router.get("/marche/prix")
def lister_prix_marche(crop:str|None=None,region:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    sql="SELECT id,crop,region,price_per_t,currency,source,observed_at FROM rotation_market_prices WHERE user_id=:u"
    params={"u":user.id}
    if crop: sql+=" AND crop=:crop"; params["crop"]=crop
    if region: sql+=" AND region=:region"; params["region"]=region
    sql+=" ORDER BY observed_at DESC LIMIT 500"
    try: rows=db.execute(text(sql),params).mappings().all()
    except Exception as exc: raise HTTPException(503,"Table marché absente : appliquer la migration 006") from exc
    return {"items":[dict(x) for x in rows]}

@router.post("/donnees/importer")
def importer(payload:ImportRequest,db:Session=Depends(get_db),user=Depends(get_current_user)):
    try: rows=parse_csv(payload.csv_content)
    except ValueError as exc: raise HTTPException(422,str(exc))
    if not rows: raise HTTPException(422,"Le CSV ne contient aucune ligne")
    try:
        db.execute(text("INSERT INTO rotation_import_batches (user_id,dataset,row_count,payload_json) VALUES (:u,:d,:n,:j)"),{"u":user.id,"d":payload.dataset,"n":len(rows),"j":json.dumps(rows,ensure_ascii=False)})
        db.commit()
    except Exception as exc:
        db.rollback(); raise HTTPException(503,"Table d'import absente : appliquer la migration 006") from exc
    return {"imported_rows":len(rows),"dataset":payload.dataset,"note":"Import brut mis en quarantaine; validation du schéma et approbation requises avant utilisation agronomique."}
