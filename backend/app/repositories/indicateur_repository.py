from fastapi import HTTPException
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from app.models.parcelle import Parcelle
from app.models.indicateur import IndicateurCalculation

def get_owned_parcelle(db: Session, parcelle_id: int, farmer_id: int) -> Parcelle:
    obj = db.scalar(select(Parcelle).where(Parcelle.id == parcelle_id, Parcelle.farmer_id == farmer_id))
    if obj is None:
        raise HTTPException(status_code=404, detail="Parcelle introuvable")
    return obj

def get_calculation(db: Session, calculation_id: int, farmer_id: int):
    obj = db.scalar(select(IndicateurCalculation).where(IndicateurCalculation.id == calculation_id, IndicateurCalculation.farmer_id == farmer_id))
    if obj is None:
        raise HTTPException(status_code=404, detail="Calcul introuvable")
    return obj

def latest_for_parcelle(db: Session, parcelle_id: int, farmer_id: int):
    get_owned_parcelle(db, parcelle_id, farmer_id)
    return db.scalars(select(IndicateurCalculation).where(IndicateurCalculation.parcelle_id == parcelle_id, IndicateurCalculation.farmer_id == farmer_id).order_by(desc(IndicateurCalculation.created_at), desc(IndicateurCalculation.id))).first()

def history_for_parcelle(db: Session, parcelle_id: int, farmer_id: int, limit: int = 50):
    get_owned_parcelle(db, parcelle_id, farmer_id)
    return list(db.scalars(select(IndicateurCalculation).where(IndicateurCalculation.parcelle_id == parcelle_id, IndicateurCalculation.farmer_id == farmer_id).order_by(desc(IndicateurCalculation.created_at), desc(IndicateurCalculation.id)).limit(limit)))
