# API 6 — Détail d’un calcul

Ce ZIP ajoute uniquement l'endpoint indiqué. Il est conçu pour le backend `adapting-farms-backend` et réutilise l'authentification fermier (`get_current_user`), SQLAlchemy et le modèle `Parcelle` déjà installé.

## Installation
1. Décompresser à la racine du backend (fusionner les dossiers `app/`, `bd/`, `common/`, `indicateurs_service/`, `zonal_service/`).
2. Ajouter l'import du modèle dans `app/models/__init__.py` : `from app.models.indicateur import IndicateurCalculation`.
3. Ajouter le routeur dans `app/api/router.py` :

```python
from app.api.v1 import indicateurs_calcul_detail
api_router.include_router(indicateurs_calcul_detail.router)
```

4. Exécuter la migration `database/migrations/004_create_indicateurs.sql` dans la même base MySQL que `users` et `parcelles`.
5. Installer les dépendances indiquées ci-dessous.
6. Redémarrer : `python -m uvicorn app.main:app --reload` puis ouvrir `/docs`.

## Configuration du catalogue cultures
Le code du projet lit le catalogue dans `nasa_challenge.culture` par défaut. Définir si besoin `CULTURE_MYSQL_HOST`, `CULTURE_MYSQL_PORT`, `CULTURE_MYSQL_USER`, `CULTURE_MYSQL_PASSWORD`, `CULTURE_MYSQL_DATABASE` et `CULTURE_MYSQL_TABLE`. Ces paramètres sont séparés de la base principale du backend.

## Dépendances
`pip install pandas numpy scipy requests pymysql earthengine-api`

Pour l'API de calcul : définir `GEE_PROJECT`. En serveur, définir aussi `GEE_SERVICE_ACCOUNT` et `GEE_KEY_FILE`. Google Earth Engine doit être activé et autorisé.

## Sécurité et limites
Les routes sont protégées par le JWT du fermier. Les résultats et historiques sont filtrés par `farmer_id`. La migration suppose que `users` et `parcelles` existent. Les appels Earth Engine / NASA / SoilGrids nécessitent un accès réseau et une configuration GEE réelle ; la création du ZIP ne constitue pas un test de connexion live.
