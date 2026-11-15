# Pipeline des données agricoles externes

La migration `007_create_external_agri_datasets.sql` crée `external_agri_datasets` dans la base configurée par `MYSQL_DATABASE` (par défaut `agrisense`). MySQL devient la source de vérité; les fichiers JSON `data/external_agri/raw/` et `normalized/` restent des copies d'audit.

## Mise en service

1. Vérifier le `.env` local sans partager ses secrets : `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`.
2. Vérifier l'état : `python scripts/migrate.py status`.
3. Faire une sauvegarde MySQL vérifiée.
4. Si et seulement si la base est une base neuve vide conforme aux règles du runner, appliquer les migrations : `python scripts/migrate.py apply --backup-confirmed`.
   - Le runner refuse volontairement une base non vide sans journal de migrations. Ne pas contourner cette protection; établir une baseline manuelle après audit/backup si nécessaire.
5. Importer les anciens JSON si le dossier en contient : `python scripts/sync_external_agri_files.py`.
6. Lancer l'API, se connecter, puis appeler `GET /api/v1/agri-external-data/pipeline/status`.

## Cycle d'une donnée

- Collecte API implémentée : World Bank, FAOSTAT, NASA POWER et SoilGrids. Aucune disponibilité en direct n'est garantie par les tests.
- Pour World Bank, les paramètres de requête acceptés sont `date` (`AAAA` ou `AAAA:AAAA`), `page` (entier positif) et `per_page` (1–1000); les autres paramètres sont rejetés explicitement. Les options utilisées sont conservées dans les métadonnées du dataset.
- GPM IMERG, SMAP L4 et MODIS sont répertoriés comme bloqués tant que le déploiement n'est pas configuré pour Google Earth Engine. Le collecteur ne tente ni initialisation GEE ni appel au catalogue/API.
- Import documentaire : CSV, XLSX et JSON via `POST /api/v1/agri-external-data/import`; la limite existante de 15 Mo est conservée. Excel est lu en mode lecture seule sans évaluer les formules.
- Chaque collecte/import conserve la réponse/charge d'origine séparément des enregistrements normalisés, avec provenance, unités, dates ou profondeurs, coordonnées si disponibles, sémantique (statistique nationale, estimation ou interpolation) et éléments de qualité.
- Les datasets identiques d'une même source sont détectés avant insertion; l'existant est retourné et n'est pas remplacé. L'insertion MySQL reste le prérequis à la copie dans `raw/` et `normalized/`; une erreur de persistance n'est pas masquée.
- Tout dataset commence avec `quality_status=needs_validation`. Un humain doit contrôler source, licence, unités, définition, période et couverture, puis confirmer via `POST /api/v1/agri-external-data/datasets/{dataset_id}/validate`.
- La validation signifie revue documentaire, pas validation agronomique automatique. Aucun dataset n'est injecté silencieusement dans le moteur de rotation.
- EcoCrop, ONAGRI, DGEDA, FAO FPMA et World Bank Pink Sheet restent des sources documentaires à importer manuellement; pas de scraping automatique configuré.
- GEE reste une dépendance séparée; les connecteurs d'indicateurs existants ne sont pas modifiés ni invoqués par cette pipeline.
- Les réglages optionnels `GEE_PROJECT`, `GEE_SERVICE_ACCOUNT` et `GEE_KEY_FILE` sont chargés par `app.core.config.Settings` depuis `.env` ou l'environnement. Pour un serveur, configurez l'ID du projet, l'adresse du compte de service et le chemin local vers son fichier de clé; le compte doit avoir accès à Earth Engine. Le compte et le chemin de clé doivent être fournis ensemble. Ne copiez jamais le contenu JSON/la clé privée dans `.env`, les logs ou le dépôt; protégez le fichier de clé local. `.env.example` ne contient que des valeurs fictives.

## Endpoints

- `GET /api/v1/agri-external-data/sources`
- `GET /api/v1/agri-external-data/pipeline/status`
- `POST /api/v1/agri-external-data/collect/{source_id}`
- `POST /api/v1/agri-external-data/import`
- `GET /api/v1/agri-external-data/datasets`
- `GET /api/v1/agri-external-data/datasets/{dataset_id}`
- `POST /api/v1/agri-external-data/datasets/{dataset_id}/validate`

Toutes les routes sont protégées par JWT.
