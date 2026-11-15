# Intégration `agri_external_data_collector`

Cette intégration ajoute une collecte séparée des données agricoles externes, sans remplacer les modules existants Parcelles, Sol et Indicateurs.

## API (préfixe final `/api/v1`)

Toutes les routes nécessitent le JWT existant.

- `GET /api/v1/agri-external-data/sources` : catalogue et nature des sources.
- `POST /api/v1/agri-external-data/collect/world_bank_tunisia_agriculture` : récupère les séries World Bank configurées (indicateurs par défaut ou liste personnalisée).
- `POST /api/v1/agri-external-data/collect/faostat_crop_production` : collecte FAOSTAT QCL avec paramètres par défaut ou personnalisés.
- `GET /api/v1/agri-external-data/datasets` : liste des collectes/imports.
- `GET /api/v1/agri-external-data/datasets/{dataset_id}` : détail et enregistrements.
- `POST /api/v1/agri-external-data/import` : import CSV/JSON documenté, multipart `source_id`, `file`, `observed_at` facultatif.

Exemple du corps pour World Bank :

```json
{"indicators":["AG.YLD.CREL.KG","AG.LND.ARBL.HA"],"timeout":30}
```

## Sources intégrées / répertoriées

- World Bank API : indicateurs nationaux (pas des données de parcelle).
- FAOSTAT API QCL : production, rendements et superficies, selon couverture réelle de l'API.
- FAO EcoCrop, ONAGRI, DGEDA et FAO FPMA : répertoriés comme sources documentaires. Ils ne sont PAS scrapés automatiquement car les formats, accès et conditions de réutilisation doivent être vérifiés; import CSV/JSON disponible.
- World Bank Commodity Markets : référence de prix internationaux, pas un prix producteur tunisien.

## Stockage et traçabilité

Les réponses brutes sont enregistrées sous `data/external_agri/raw/`; les métadonnées normalisées sous `data/external_agri/normalized/`. Chaque collecte porte un identifiant, le fournisseur, les URL réellement appelées, l'heure UTC, les paramètres, le nombre de lignes et le statut `needs_validation`.

Les données ne sont volontairement PAS injectées automatiquement dans le moteur de rotation : une série nationale, un prix international ou une valeur de référence ne doit pas être assimilé à une mesure de parcelle. L'étape de validation/harmonisation agronomique devra mapper les champs, unités, dates, échelle spatiale et qualité avant scoring.

## Installation

1. Décompresser ce ZIP dans ton projet ou copier les fichiers en conservant les chemins.
2. Depuis le dossier du backend, activer le même environnement virtuel que celui utilisé pour Uvicorn.
3. Installer/mettre à jour les dépendances : `python -m pip install -r requirements.txt`.
4. Relancer : `python -m uvicorn app.main:app --reload`.
5. Ouvrir `http://127.0.0.1:8000/docs`, se connecter avec Authorize et chercher le tag **Agriculture - Données externes**.

Aucune migration SQL n'est nécessaire. Les fichiers collectés restent locaux. Ajouter `data/external_agri/` à `.gitignore` si tu ne veux pas versionner les jeux de données.

## Limites importantes

- Une collecte en direct dépend de la disponibilité des services tiers et de leurs paramètres/API au moment de l'appel.
- Les données nationales/internationales ont une résolution différente des données de parcelle.
- Vérifier la licence, les unités, les définitions, la période et la couverture avant d'utiliser les données pour recommander une rotation.
- Les sources marquées `manual_reference` renvoient volontairement une erreur en collecte automatique; utiliser l'import CSV/JSON après contrôle du document source.
- Ce module ne fait pas de scraping agressif de sites web et ne contourne aucune authentification ou restriction.

## Vérification locale

`python -m compileall app/integrations/agri_external_data_collector app/services/agri_external_data_collector app/api/v1/agri_external_data.py`
