from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories import parcelle_repository as repo


def get_owned_parcelle(db: Session, parcelle_id: int, farmer_id: int):
    item = repo.get_for_farmer(db, parcelle_id, farmer_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcelle introuvable")
    return item


def create_parcelle(db: Session, farmer_id: int, data: dict):
    return repo.create(db, farmer_id, data)


def update_parcelle(db: Session, parcelle_id: int, farmer_id: int, data: dict):
    item = get_owned_parcelle(db, parcelle_id, farmer_id)
    return repo.update(db, item, data)


def delete_parcelle(db: Session, parcelle_id: int, farmer_id: int):
    item = get_owned_parcelle(db, parcelle_id, farmer_id)
    repo.delete(db, item)


def add_culture(db: Session, parcelle_id: int, farmer_id: int, data: dict):
    get_owned_parcelle(db, parcelle_id, farmer_id)
    return repo.add_culture(db, parcelle_id, data)


def add_constraint(db: Session, parcelle_id: int, farmer_id: int, data: dict):
    get_owned_parcelle(db, parcelle_id, farmer_id)
    return repo.add_constraint(db, parcelle_id, data)
