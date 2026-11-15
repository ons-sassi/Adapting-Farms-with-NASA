# Module FastAPI — Gestion des données du sol

Ce dossier est un **patch** à intégrer dans le backend existant. Il ne remplace pas le projet complet.

## 1. Prérequis

- Le module Authentification et le module Parcelles doivent déjà être installés.
- La table `users` et la table `parcelles` doivent exister.
- Le backend doit utiliser les chemins présents dans le projet : `app.db.base.Base`,
  `app.core.dependencies.get_db`, `app.core.dependencies.get_current_user`,
  `app.models.parcelle.Parcelle` et `Parcelle.farmer_id`.

Dans le terminal, depuis le dossier `adapting-farms-backend` :

```bash
python -m pip install python-multipart openpyxl
```

Ajoutez aussi ces dépendances à votre `requirements.txt` si elles n'y figurent pas :

```text
python-multipart
openpyxl>=3.1
```

## 2. Copier les fichiers

Copiez le contenu du dossier `app/` de cette archive dans le dossier `app/` de votre backend, en fusionnant les dossiers.

Ajoutez l'import du modèle dans `app/models/__init__.py` sans supprimer les imports existants :

```python
from app.models.sol import SoilAnalysis
```

## 3. Enregistrer le routeur

Dans `app/api/router.py`, conservez les routeurs déjà présents (health, auth et parcelles), puis ajoutez :

```python
from app.api.v1 import sol
api_router.include_router(sol.router, prefix="/api/v1")
```

Si votre variable de routeur principal ne s'appelle pas `api_router`, adaptez uniquement ce nom.

## 4. Exécuter la migration

Après la migration `002_create_parcelles.sql`, exécutez :

```sql
SOURCE database/migrations/003_create_sol.sql;
```

Exécutez la commande dans MySQL Workbench ou adaptez-la à votre outil SQL.

## 5. Routes disponibles

| Méthode | Route | Description |
|---|---|---|
| POST | `/api/v1/sol/` | Ajouter une analyse |
| GET | `/api/v1/sol/parcelle/{parcelle_id}` | Lister les analyses d'une parcelle |
| GET | `/api/v1/sol/{analysis_id}` | Consulter une analyse |
| PUT | `/api/v1/sol/{analysis_id}` | Modifier une analyse |
| DELETE | `/api/v1/sol/{analysis_id}` | Supprimer une analyse |
| GET | `/api/v1/sol/template` | Télécharger le modèle CSV |
| POST | `/api/v1/sol/import` | Importer un fichier CSV ou XLSX |

Toutes les routes métier sont protégées par JWT et vérifient que la parcelle appartient au fermier connecté.

## 6. Format d'import CSV / Excel

La première ligne doit contenir les noms de colonnes suivants :

`parcelle_id, ph, organic_matter_percent, texture, nitrogen_mg_kg, phosphorus_mg_kg, potassium_mg_kg, salinity_ds_m, limestone_percent, cec_cmol_kg, sampled_at, source, notes`

- `parcelle_id` est obligatoire et doit correspondre à une parcelle du fermier connecté.
- `sampled_at` utilise le format `AAAA-MM-JJ`.
- `source` vaut `manual`, `laboratory` ou `soilgrids`.
- Les valeurs numériques peuvent être laissées vides.
- L'import est atomique : si une ligne est invalide ou concerne une parcelle qui ne vous appartient pas, aucune ligne du fichier n'est enregistrée.
- Les valeurs `soilgrids` représentent des estimations et ne doivent pas être présentées comme des analyses de laboratoire.

Téléchargez le modèle via `GET /api/v1/sol/template`.

## 7. Lancement et test

```bash
python -m uvicorn app.main:app --reload
```

Ouvrez `http://127.0.0.1:8000/docs`, connectez-vous avec le bouton **Authorize**, puis testez les routes `/api/v1/sol`.

Commencez par créer une analyse sur une parcelle existante. Testez ensuite la consultation, la modification, le téléchargement du modèle et l'import.
