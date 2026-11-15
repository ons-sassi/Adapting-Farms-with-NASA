"""Fonctions déterministes pour l'empreinte des snapshots."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: dict[str, Any]) -> str:
    """Sérialisation stable ; échoue si le contenu n'est pas du JSON valide."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_json_default,
    )


def _json_default(value: Any):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Type non sérialisable dans le snapshot: {type(value).__name__}")


def calculate_content_hash(payload: dict[str, Any], source_metadata: dict[str, Any]) -> str:
    content = canonical_json({"payload": payload, "source_metadata": source_metadata})
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
