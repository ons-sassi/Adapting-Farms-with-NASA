# FastAPI — Audit des snapshots de rotation

Ce patch ajoute deux opérations en lecture seule. Il suppose que le patch `rotation_snapshots_fastapi_patch.zip` et sa migration SQL ont déjà été installés.

## Endpoints

- `GET /api/v1/rotation/parcelles/{parcelle_id}/snapshots/audit/comparer?reference_id=1&cible_id=2`
  - Compare les données et métadonnées de deux snapshots de la même parcelle.
  - Retourne les champs ajoutés, supprimés ou modifiés, les changements de provenance/métadonnées et l'évolution de `qualite` si elle est présente dans le payload.
- `GET /api/v1/rotation/parcelles/{parcelle_id}/snapshots/{snapshot_id}/audit-integrite`
  - Recalcule le SHA-256 et compare avec le hash stocké.

## Sécurité et limites

- Authentification fermier obligatoire ; les deux snapshots doivent appartenir au fermier et à la parcelle demandés.
- Aucun endpoint ne modifie ou ne supprime un snapshot.
- Les tableaux JSON sont comparés comme des valeurs complètes, pas élément par élément.
- L'audit ne prouve pas l'exactitude scientifique des données ; il détecte les différences et l'altération du contenu par rapport au hash.
- Installer ce patch après le patch Snapshots. Le `app/api/router.py` fourni conserve les routeurs fusion et snapshots.

## Exemple

`GET /api/v1/rotation/parcelles/12/snapshots/audit/comparer?reference_id=4&cible_id=5`

`GET /api/v1/rotation/parcelles/12/snapshots/5/audit-integrite`
