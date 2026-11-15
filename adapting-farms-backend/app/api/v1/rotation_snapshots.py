"""API de snapshots versionnés et immuables des données de rotation."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.engine.rotation.snapshot_engine import calculate_content_hash
from app.models.parcelle import Parcelle
from app.models.rotation_snapshot import RotationSnapshot
from app.schemas.rotation_snapshots import (
    RotationSnapshotCreate,
    RotationSnapshotListItem,
    RotationSnapshotRead,
)

router = APIRouter(prefix="/rotation", tags=["Rotation - Snapshots versionnés"])


def _owned_parcel(db: Session, parcelle_id: int, farmer_id: int, *, lock: bool = False):
    stmt = select(Parcelle).where(
        Parcelle.id == parcelle_id,
        Parcelle.farmer_id == farmer_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    parcel = db.scalar(stmt)
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcelle introuvable")
    return parcel


@router.post(
    "/parcelles/{parcelle_id}/snapshots",
    response_model=RotationSnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
def creer_snapshot_rotation(
    parcelle_id: int,
    payload: RotationSnapshotCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Enregistre une copie figée des données fusionnées et crée sa version.

    La ligne créée n'est jamais modifiée par cette API. Chaque nouvel appel crée
    une nouvelle version, même si son contenu est identique à une version antérieure.
    """
    # Verrouiller la parcelle sérialise l'attribution des versions sur MySQL.
    _owned_parcel(db, parcelle_id, current_user.id, lock=True)

    data = payload.donnees
    metadata = payload.source_metadata
    try:
        digest = calculate_content_hash(data, metadata)
    except (TypeError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"Snapshot non sérialisable: {exc}") from exc

    current_version = db.scalar(
        select(func.max(RotationSnapshot.version)).where(
            RotationSnapshot.parcelle_id == parcelle_id
        )
    ) or 0
    snapshot = RotationSnapshot(
        parcelle_id=parcelle_id,
        farmer_id=current_user.id,
        version=current_version + 1,
        content_hash=digest,
        payload=data,
        source_metadata=metadata,
    )
    db.add(snapshot)
    try:
        db.commit()
        db.refresh(snapshot)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflit de création de version. Réessayez la création du snapshot.",
        ) from exc
    return snapshot


@router.get(
    "/parcelles/{parcelle_id}/snapshots",
    response_model=list[RotationSnapshotListItem],
)
def lister_snapshots_rotation(
    parcelle_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _owned_parcel(db, parcelle_id, current_user.id)
    return list(db.scalars(
        select(RotationSnapshot)
        .where(
            RotationSnapshot.parcelle_id == parcelle_id,
            RotationSnapshot.farmer_id == current_user.id,
        )
        .order_by(desc(RotationSnapshot.version))
        .offset(offset)
        .limit(limit)
    ).all())


@router.get(
    "/parcelles/{parcelle_id}/snapshots/{snapshot_id}",
    response_model=RotationSnapshotRead,
)
def obtenir_snapshot_rotation(
    parcelle_id: int,
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _owned_parcel(db, parcelle_id, current_user.id)
    snapshot = db.scalar(select(RotationSnapshot).where(
        RotationSnapshot.id == snapshot_id,
        RotationSnapshot.parcelle_id == parcelle_id,
        RotationSnapshot.farmer_id == current_user.id,
    ))
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot introuvable")
    return snapshot
