from fastapi import APIRouter, File, HTTPException, UploadFile

from integrations.errors import ExternalSourceError
from services.document_extractor import UnsupportedDocumentError, extract_document

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.post("/extract")
def extract(file: UploadFile = File(...)) -> dict:
    """PDF ou image -> JSON de toutes les données trouvées."""
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Fichier trop volumineux (20 Mo maximum).")
    try:
        return extract_document(content)
    except UnsupportedDocumentError as exc:
        raise HTTPException(415, str(exc))
    except ExternalSourceError as exc:
        raise HTTPException(502, str(exc))
