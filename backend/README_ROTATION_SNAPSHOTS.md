# FastAPI — Snapshots versionnés des données de rotation

Ce patch ajoute un stockage append-only des données fusionnées utilisées pour produire une recommandation.

## Fichiers
- `app/models/rotation_snapshot.py` : table SQLAlchemy.
- `app/schemas/rotation_snapshots.py` : contrats Pydantic.
- `app/engine/rotation/snapshot_engine.py` : empreinte SHA-256 déterministe.
- `app/api/v1/rotation_snapshots.py` : création, liste et lecture.
- `app/api/router.py` : enregistrement du routeur (inclut aussi `rotation_donnees`, livré par le patch de fusion précédent).
- `database/migrations/005_create_rotation_data_snapshots.sql` : table et triggers d'immutabilité MySQL.

## Pré-requis
1. Le patch précédent `rotation_fusion_normalisation_donnees_fastapi_patch.zip` doit déjà être intégré, car `app/api/router.py` enregistre son module `rotation_donnees`.
2. La migration SQL 005 doit être exécutée sur MySQL avant d'appeler l'API.
3. L'utilisateur doit être authentifié et propriétaire de la parcelle.

## Routes
- `POST /api/v1/rotation/parcelles/{parcelle_id}/snapshots` — crée une nouvelle version.
- `GET /api/v1/rotation/parcelles/{parcelle_id}/snapshots?limit=20&offset=0` — liste les versions, de la plus récente à la plus ancienne.
- `GET /api/v1/rotation/parcelles/{parcelle_id}/snapshots/{snapshot_id}` — lit une version précise.

Aucune route de modification ou suppression n'est exposée. Les triggers MySQL bloquent également UPDATE et DELETE directs. Les clés étrangères utilisent RESTRICT (pas de suppression en cascade) pour préserver l'historique.

## Exemple de création
Utiliser la réponse complète de `POST /api/v1/rotation/parcelles/{parcelle_id}/donnees/fusionner` dans le champ `donnees` :

```json
{
  "donnees": {
    "donnees_fusionnees": {"ph": 7.1, "organic_matter_percent": 1.8},
    "provenance": {"ph": {"source": "farmer", "quality_status": "verified"}},
    "conflits_a_verifier": {},
    "qualite": {"statut": "exploitable"}
  },
  "source_metadata": {
    "pipeline": "rotation_data_fusion",
    "schema_version": "1.0",
    "commentaire": "Snapshot avant scoring"
  }
}
```

La réponse inclut `version`, `content_hash` et `created_at`. Le hash SHA-256 est calculé sur le contenu et les métadonnées sérialisés de façon canonique. Deux snapshots identiques auront le même hash, mais recevront des numéros de version différents.

## Test local
La compilation syntaxique est vérifiée. Le test d'intégration HTTP/MySQL reste à faire dans l'environnement du projet après exécution de la migration.
