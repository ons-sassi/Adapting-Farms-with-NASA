from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.repositories.indicateur_repository import get_calculation
from app.services.indicateur_service import serialize
router = APIRouter(prefix="/indicateurs", tags=["Indicateurs - Détail calcul"])
@router.get("/calculs/{calcul_id}")
def detail_calcul(calcul_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return serialize(get_calculation(db, calcul_id, current_user.id))
