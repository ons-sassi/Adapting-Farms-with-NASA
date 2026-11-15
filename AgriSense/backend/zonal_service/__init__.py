"""Service « zonal » : données brutes moyennées sur le polygone de la parcelle (aucun indice)."""
from .serialisation import donnees_from_json, donnees_to_json
from .zonal import get_donnees_zonales

__all__ = ["get_donnees_zonales", "donnees_to_json", "donnees_from_json"]
