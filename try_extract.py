"""Test rapide sans serveur :   python try_extract.py rapport.pdf
À lancer à la racine du backend (là où se trouve settings.py)."""
import json
import sys

from integrations.errors import ExternalSourceError
from services.document_extractor import UnsupportedDocumentError, extract_document

if len(sys.argv) != 2:
    sys.exit("Usage : python try_extract.py <fichier.pdf|png|jpg|webp>")

try:
    with open(sys.argv[1], "rb") as f:
        result = extract_document(f.read())
except (ExternalSourceError, UnsupportedDocumentError) as exc:
    sys.exit(f"Erreur : {exc}")

print(json.dumps(result, ensure_ascii=False, indent=2))
