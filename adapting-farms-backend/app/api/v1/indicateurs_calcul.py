from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.schemas.indicateur import CalculIndicateursCreate
from app.services.indicateur_service import calculer, serialize
router = APIRouter(prefix="/indicateurs", tags=["Indicateurs - Calcul"])
@router.post("/parcelles/{parcelle_id}/calculer", status_code=status.HTTP_201_CREATED)
def calculer_indicateurs(parcelle_id: int, data: CalculIndicateursCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    item = calculer(db, parcelle_id, current_user.id, data.culture, data.start, data.end, data.sol_mesure)
    return serialize(item)
