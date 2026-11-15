from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import get_current_user
router = APIRouter(prefix="/indicateurs", tags=["Indicateurs - Cultures"])
@router.get("/cultures")
def lister_cultures(_current_user=Depends(get_current_user)):
    try:
        from bd.cultures import lister_cultures as lire
        return {"total": len(lire()), "cultures": lire()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Catalogue MySQL des cultures indisponible: {exc}")
