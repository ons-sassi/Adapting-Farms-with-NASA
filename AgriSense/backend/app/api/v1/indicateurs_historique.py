from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.repositories.indicateur_repository import history_for_parcelle
from app.services.indicateur_service import serialize
router = APIRouter(prefix="/indicateurs", tags=["Indicateurs - Historique"])
@router.get("/parcelles/{parcelle_id}/historique")
def historique_calculs(parcelle_id: int, limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return [serialize(x) for x in history_for_parcelle(db, parcelle_id, current_user.id, limit)]
