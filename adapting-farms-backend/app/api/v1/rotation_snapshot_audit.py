"""Endpoints d'audit historique et d'intégrité des snapshots."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.engine.rotation.snapshot_audit import compare_snapshots, verify_snapshot_integrity
from app.models.parcelle import Parcelle
from app.models.rotation_snapshot import RotationSnapshot
from app.schemas.rotation_snapshot_audit import SnapshotComparisonRead, SnapshotIntegrityRead

router = APIRouter(prefix="/rotation", tags=["Rotation - Audit des snapshots"])


def _owned_parcel(db: Session, parcelle_id: int, farmer_id: int) -> None:
    parcel = db.scalar(select(Parcelle.id).where(
        Parcelle.id == parcelle_id, Parcelle.farmer_id == farmer_id
    ))
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcelle introuvable")


def _get_snapshot(db: Session, parcelle_id: int, farmer_id: int, snapshot_id: int):
    snapshot = db.scalar(select(RotationSnapshot).where(
        RotationSnapshot.id == snapshot_id,
        RotationSnapshot.parcelle_id == parcelle_id,
        RotationSnapshot.farmer_id == farmer_id,
    ))
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot introuvable pour cette parcelle")
    return snapshot


@router.get(
    "/parcelles/{parcelle_id}/snapshots/audit/comparer",
    response_model=SnapshotComparisonRead,
)
def comparer_snapshots_rotation(
    parcelle_id: int,
    reference_id: int = Query(..., gt=0, description="ID du snapshot de référence"),
    cible_id: int = Query(..., gt=0, description="ID du snapshot à comparer"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Compare deux snapshots d'une même parcelle, sans modifier les données."""
    if reference_id == cible_id:
        raise HTTPException(status_code=422, detail="Les deux snapshots doivent être différents")
    _owned_parcel(db, parcelle_id, current_user.id)
    reference = _get_snapshot(db, parcelle_id, current_user.id, reference_id)
    target = _get_snapshot(db, parcelle_id, current_user.id, cible_id)
    return compare_snapshots(reference, target)


@router.get(
    "/parcelles/{parcelle_id}/snapshots/{snapshot_id}/audit-integrite",
    response_model=SnapshotIntegrityRead,
)
def verifier_integrite_snapshot_rotation(
    parcelle_id: int,
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Vérifie que le contenu enregistré correspond à son empreinte SHA-256."""
    _owned_parcel(db, parcelle_id, current_user.id)
    snapshot = _get_snapshot(db, parcelle_id, current_user.id, snapshot_id)
    return verify_snapshot_integrity(snapshot)
