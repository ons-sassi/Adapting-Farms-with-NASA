from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.sol import SoilAnalysis


def get_by_id(db: Session, analysis_id: int):
    return db.scalar(select(SoilAnalysis).where(SoilAnalysis.id == analysis_id))


def list_for_parcelle(db: Session, parcelle_id: int):
    return list(db.scalars(
        select(SoilAnalysis).where(SoilAnalysis.parcelle_id == parcelle_id)
        .order_by(SoilAnalysis.sampled_at.desc(), SoilAnalysis.id.desc())
    ).all())


def create(db: Session, data: dict):
    obj = SoilAnalysis(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update(db: Session, obj: SoilAnalysis, data: dict):
    for key, value in data.items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete(db: Session, obj: SoilAnalysis):
    db.delete(obj)
    db.commit()
