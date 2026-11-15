from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import get_current_user
router = APIRouter(prefix="/indicateurs", tags=["Indicateurs - Cultures"])
@router.get("/cultures/{identifiant}")
def obtenir_culture(identifiant: str, _current_user=Depends(get_current_user)):
    try:
        from bd.cultures import get_culture
        return get_culture(identifiant)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Catalogue MySQL des cultures indisponible: {exc}")
