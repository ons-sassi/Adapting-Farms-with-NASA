"""Contrats API de création et consultation des snapshots de rotation."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RotationSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Envoyer ici la réponse complète de l'API de fusion, sans la recalculer.
    donnees: dict[str, Any] = Field(min_length=1)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class RotationSnapshotRead(BaseModel):
    id: int
    parcelle_id: int
    farmer_id: int
    version: int
    content_hash: str
    payload: dict[str, Any]
    source_metadata: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RotationSnapshotListItem(BaseModel):
    id: int
    parcelle_id: int
    version: int
    content_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
