"""Comparaison déterministe et vérification d'intégrité des snapshots."""
from __future__ import annotations
from typing import Any

from app.engine.rotation.snapshot_engine import calculate_content_hash


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    """Aplatit les objets JSON ; tableaux et scalaires sont comparés comme valeurs."""
    result: dict[str, Any] = {}
    if isinstance(value, dict):
        if not value and prefix:
            result[prefix] = {}
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(value[key], path))
    else:
        result[prefix or "$"] = value
    return result


def _same(a: Any, b: Any) -> bool:
    # Comparaison JSON stable (notamment pour dicts imbriqués).
    try:
        from app.engine.rotation.snapshot_engine import canonical_json
        return canonical_json({"value": a}) == canonical_json({"value": b})
    except (TypeError, ValueError):
        return a == b


def compare_snapshots(reference: Any, target: Any) -> dict[str, Any]:
    """Compare payloads et métadonnées de deux objets RotationSnapshot."""
    ref_data = _flatten(reference.payload or {})
    new_data = _flatten(target.payload or {})
    added, removed, changed = [], [], []
    for path in sorted(new_data.keys() - ref_data.keys()):
        added.append({"champ": path, "nouvelle_valeur": new_data[path]})
    for path in sorted(ref_data.keys() - new_data.keys()):
        removed.append({"champ": path, "ancienne_valeur": ref_data[path]})
    for path in sorted(ref_data.keys() & new_data.keys()):
        if not _same(ref_data[path], new_data[path]):
            changed.append({"champ": path, "ancienne_valeur": ref_data[path], "nouvelle_valeur": new_data[path]})

    ref_meta = _flatten(reference.source_metadata or {})
    new_meta = _flatten(target.source_metadata or {})
    metadata_changes = []
    for path in sorted(ref_meta.keys() | new_meta.keys()):
        before, after = ref_meta.get(path), new_meta.get(path)
        if path not in ref_meta or path not in new_meta or not _same(before, after):
            metadata_changes.append({"champ": path, "ancienne_valeur": before, "nouvelle_valeur": after})

    ref_quality = (reference.payload or {}).get("qualite", {})
    new_quality = (target.payload or {}).get("qualite", {})
    quality_changes = []
    if isinstance(ref_quality, dict) and isinstance(new_quality, dict):
        for key in sorted(ref_quality.keys() | new_quality.keys()):
            before, after = ref_quality.get(key), new_quality.get(key)
            if key not in ref_quality or key not in new_quality or not _same(before, after):
                quality_changes.append({"indicateur": key, "avant": before, "apres": after})

    return {
        "reference": {"snapshot_id": reference.id, "version": reference.version, "created_at": reference.created_at},
        "cible": {"snapshot_id": target.id, "version": target.version, "created_at": target.created_at},
        "resume": {
            "nombre_champs_ajoutes": len(added), "nombre_champs_supprimes": len(removed),
            "nombre_champs_modifies": len(changed), "nombre_metadonnees_modifiees": len(metadata_changes),
            "nombre_indicateurs_qualite_modifies": len(quality_changes),
            "identiques": not (added or removed or changed or metadata_changes),
        },
        "champs_ajoutes": added,
        "champs_supprimes": removed,
        "champs_modifies": changed,
        "metadonnees_modifiees": metadata_changes,
        "evolution_qualite": quality_changes,
    }


def verify_snapshot_integrity(snapshot: Any) -> dict[str, Any]:
    """Recalcule le hash ; ne modifie jamais le snapshot."""
    calculated = calculate_content_hash(snapshot.payload or {}, snapshot.source_metadata or {})
    stored = snapshot.content_hash
    return {
        "snapshot_id": snapshot.id,
        "version": snapshot.version,
        "integrite_valide": calculated == stored,
        "hash_enregistre": stored,
        "hash_recalcule": calculated,
    }
