from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.repositories.indicateur_repository import latest_for_parcelle
from app.services.indicateur_service import serialize
router = APIRouter(prefix="/indicateurs", tags=["Indicateurs - Résultats"])
@router.get("/parcelles/{parcelle_id}/resultats")
def derniers_resultats(parcelle_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    item = latest_for_parcelle(db, parcelle_id, current_user.id)
    if item is None:
        raise HTTPException(status_code=404, detail="Aucun calcul disponible pour cette parcelle")
    return serialize(item)
