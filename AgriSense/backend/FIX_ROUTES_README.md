# Correction des routes FastAPI

Le préfixe `/api/v1` est appliqué une seule fois dans `app/main.py` via `settings.api_v1_prefix`.
Le routeur central n'ajoute donc plus `/api/v1` une deuxième fois.

Routes attendues :
- `/api/v1/sol/...`
- `/api/v1/indicateurs/...`
- `/api/v1/agri-external-data/...`
- `/api/v1/agri-external-data/datasets/{dataset_id}/validate`
- `/api/v1/rotation/parcelles/{parcelle_id}/context`

Le endpoint Rotation assemble les données existantes. Il ne génère pas encore de rotation agronomique.

Le fichier `.env` n'est pas inclus dans ce ZIP afin de ne pas redistribuer de secrets. Conserve ton `.env` local.
