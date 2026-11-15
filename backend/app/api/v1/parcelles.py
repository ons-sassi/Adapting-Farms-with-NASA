from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories import parcelle_repository as repo
from app.schemas.parcelle import (
    ConstraintCreate, ConstraintResponse, CultureCreate, CultureResponse,
    ParcelleCreate, ParcelleResponse, ParcelleUpdate,
)
from app.services import parcelle_service as service

router = APIRouter(prefix="/parcelles", tags=["Parcelles"])


@router.post("/", response_model=ParcelleResponse, status_code=status.HTTP_201_CREATED)
def create_parcelle(
    data: ParcelleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_parcelle(db, current_user.id, data.model_dump())


@router.get("/", response_model=list[ParcelleResponse])
def list_parcelles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return repo.list_for_farmer(db, current_user.id)


@router.get("/{parcelle_id}", response_model=ParcelleResponse)
def get_parcelle(
    parcelle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_owned_parcelle(db, parcelle_id, current_user.id)


@router.put("/{parcelle_id}", response_model=ParcelleResponse)
def update_parcelle(
    parcelle_id: int,
    data: ParcelleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.update_parcelle(
        db, parcelle_id, current_user.id, data.model_dump(exclude_unset=True)
    )


@router.delete("/{parcelle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parcelle(
    parcelle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_parcelle(db, parcelle_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{parcelle_id}/history", response_model=CultureResponse, status_code=201)
def add_crop_history(
    parcelle_id: int,
    data: CultureCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.add_culture(db, parcelle_id, current_user.id, data.model_dump())


@router.get("/{parcelle_id}/history", response_model=list[CultureResponse])
def get_crop_history(
    parcelle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = service.get_owned_parcelle(db, parcelle_id, current_user.id)
    return item.cultures


@router.post("/{parcelle_id}/constraints", response_model=ConstraintResponse, status_code=201)
def add_parcelle_constraint(
    parcelle_id: int,
    data: ConstraintCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.add_constraint(db, parcelle_id, current_user.id, data.model_dump())


@router.get("/{parcelle_id}/constraints", response_model=list[ConstraintResponse])
def get_parcelle_constraints(
    parcelle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = service.get_owned_parcelle(db, parcelle_id, current_user.id)
    return item.constraints
