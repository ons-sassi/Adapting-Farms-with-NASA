"""Contrats de réponse pour l'audit des snapshots."""
from typing import Any
from pydantic import BaseModel, ConfigDict


class SnapshotIntegrityRead(BaseModel):
    snapshot_id: int
    version: int
    integrite_valide: bool
    hash_enregistre: str
    hash_recalcule: str


class SnapshotComparisonRead(BaseModel):
    reference: dict[str, Any]
    cible: dict[str, Any]
    resume: dict[str, Any]
    champs_ajoutes: list[dict[str, Any]]
    champs_supprimes: list[dict[str, Any]]
    champs_modifies: list[dict[str, Any]]
    metadonnees_modifiees: list[dict[str, Any]]
    evolution_qualite: list[dict[str, Any]]
    model_config = ConfigDict(from_attributes=True)
