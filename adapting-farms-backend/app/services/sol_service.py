from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.parcelle import Parcelle
from app.models.sol import SoilAnalysis


def get_owned_parcelle(db: Session, parcelle_id: int, farmer_id: int):
    return db.scalar(select(Parcelle).where(
        Parcelle.id == parcelle_id,
        Parcelle.farmer_id == farmer_id
    ))


def get_owned_analysis(db: Session, analysis_id: int, farmer_id: int):
    return db.scalar(
        select(SoilAnalysis)
        .join(Parcelle, SoilAnalysis.parcelle_id == Parcelle.id)
        .where(SoilAnalysis.id == analysis_id, Parcelle.farmer_id == farmer_id)
    )
