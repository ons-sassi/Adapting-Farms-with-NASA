from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.parcelle import Parcelle, ParcelleCulture, ParcelleConstraint


def list_for_farmer(db: Session, farmer_id: int) -> list[Parcelle]:
    stmt = (
        select(Parcelle)
        .where(Parcelle.farmer_id == farmer_id)
        .options(selectinload(Parcelle.cultures), selectinload(Parcelle.constraints))
        .order_by(Parcelle.id.desc())
    )
    return list(db.scalars(stmt).all())


def get_for_farmer(db: Session, parcelle_id: int, farmer_id: int) -> Parcelle | None:
    stmt = (
        select(Parcelle)
        .where(Parcelle.id == parcelle_id, Parcelle.farmer_id == farmer_id)
        .options(selectinload(Parcelle.cultures), selectinload(Parcelle.constraints))
    )
    return db.scalars(stmt).first()


def create(db: Session, farmer_id: int, data: dict) -> Parcelle:
    item = Parcelle(farmer_id=farmer_id, **data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update(db: Session, item: Parcelle, data: dict) -> Parcelle:
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete(db: Session, item: Parcelle) -> None:
    db.delete(item)
    db.commit()


def add_culture(db: Session, parcelle_id: int, data: dict) -> ParcelleCulture:
    item = ParcelleCulture(parcelle_id=parcelle_id, **data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def add_constraint(db: Session, parcelle_id: int, data: dict) -> ParcelleConstraint:
    item = ParcelleConstraint(parcelle_id=parcelle_id, **data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
