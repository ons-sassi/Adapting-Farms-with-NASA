# Vérification de la collecte de données et du stockage MySQL (15/11/2026)

Tests faits sur **MySQL 8.0.46** (même version majeure que `agrisense_backup.sql`, MySQL 8.0.43),
base vide + migrations 001 à 008. Les API externes n'étaient pas joignables depuis l'environnement
de test : les réponses HTTP ont été simulées avec les **vraies réponses archivées** dans
`data/external_agri/raw/` (World Bank, NASA POWER) et le format documenté (SoilGrids, FAOSTAT).
Pour le test en direct : `python scripts/check_data_sources.py` (voir plus bas).

## 1. Trois circuits de données distincts

| Circuit | Sources | Code | Stockage MySQL |
|---|---|---|---|
| A. Données externes | World Bank, FAOSTAT, NASA POWER, SoilGrids (API) ; ONAGRI, DGEDA, EcoCrop, FAO FPMA, Pink Sheet (import manuel CSV/XLSX/JSON) | `app/integrations/agri_external_data_collector/` + routes `/agri-external-data/*` | `agrisense.external_agri_datasets` (+ copies JSON `data/external_agri/raw|normalized`) |
| B. Indicateurs satellite | NASA POWER, SoilGrids (REST) ; GPM IMERG, SMAP L4, MODIS, SRTM, MERIT (Google Earth Engine) | `common/connectors.py`, `indicateurs_service/`, `zonal_service/` + routes `/indicateurs/*` | `agrisense.indicateur_calculations` (résultat JSON par parcelle) |
| C. Catalogue cultures | CSV EcoCrop + FAO-56 + AquaCrop | `bd/connection.py`, `bd/mysql_ingestor.py`, `bd/cultures.py` | `nasa_challenge.culture` |

`app/integrations/nasa/*.py` et `app/integrations/soilgrids/client.py` sont des fichiers vides (1 ligne) :
le vrai code est dans `common/connectors.py` et dans le collecteur.

**Il n'y a pas de scraping de sites web** : ONAGRI, DGEDA (agriculture.tn), FAO FPMA, EcoCrop et
World Bank Pink Sheet sont déclarés « import documentaire contrôlé ». Appeler leur collecte renvoie
volontairement une erreur 422.

## 2. Résultats

| Vérification | Résultat |
|---|---|
| Migrations 001–008 sur MySQL 8 vide | OK |
| Import des 2 anciens JSON (`scripts/sync_external_agri_files.py`) | OK : 2 datasets ; 2e passage = 0 importé, 2 ignorés |
| Collecte World Bank (2 indicateurs) → MySQL | OK : 50 lignes, provenance + qualité ; avertissement « pas d'unité » (normal : World Bank n'en donne pas) |
| Collecte NASA POWER → MySQL | OK : 3 jours, unités, altitude, -999 → null |
| Collecte SoilGrids → MySQL | OK après correction (voir 3) |
| Collecte FAOSTAT → MySQL | OK avec réponse simulée ; **en direct non vérifié** (expirait lors des tests de l'équipe) |
| Doublons (même collecte 2 fois) | OK : détecté, même `dataset_id`, rien de réinséré |
| Validation humaine `POST /datasets/{id}/validate` | OK : `quality_status = validated` en base et dans le JSON |
| Import CSV ONAGRI par l'API | OK : 2 lignes, `needs_validation` |
| Routes sans jeton JWT | 401 (protégées) |
| GPM / SMAP / MODIS | Bloqués proprement tant que `GEE_PROJECT` est vide (message clair, 503) |
| Calcul d'indicateurs → `indicateur_calculations` | Stockage OK avec un moteur simulé ; calcul réel non testable sans compte Earth Engine |
| Connecteurs `fetch_power` / `fetch_soilgrids` | OK : parsing, -999 → NaN, conversion d_factor, moyenne 0–100 cm |
| Catalogue → `nasa_challenge.culture` | OK après ajout de la table (voir 3) : 13 cultures insérées, 28 mises en quarantaine, 2e import idempotent |

## 3. Problèmes trouvés et corrigés

1. **Table `nasa_challenge.culture` jamais créée** : l'importeur refuse (à juste titre) de créer une
   table, mais aucun script SQL ne la créait → le moteur d'indicateurs ne pouvait jamais trouver une
   culture. Ajouté : `database/catalogue/001_create_culture.sql`.
2. **CSV du catalogue absent** (`bd/data/cultures_completes_8_especes_v6.csv`). Ajouté :
   `bd/prepare_culture_csv.py` qui fabrique le CSV + le manifeste à partir de `data/catalog/`
   (noms français inclus pour que `get_culture("orge")` marche) et option `--csv` dans `bd/connection.py`.
3. **SoilGrids stocké sans conversion** dans le collecteur externe : `phh2o = 81` (unité « pH*10 »)
   au lieu de pH 8.1, `clay = 285` g/kg au lieu de 28.5 %. Corrigé : `values` est maintenant dans
   l'unité cible (division par `d_factor`, comme `common/connectors.py`) ; les valeurs brutes restent
   dans `values_raw` / `units_raw`. Test : `tests/test_soilgrids_units.py`.

## 4. Limites restantes (non corrigées)

- **28 cultures sur 41 sont rejetées** par l'import du catalogue car `t_base` / `gdd_maturite` manquent
  (ex. blé dur, pois chiche, lentille, fève). Le moteur d'indicateurs ne peut calculer que pour :
  betterave, soja, coton, tournesol, orge, tomate, luzerne, riz, haricot sec, pomme de terre,
  blé tendre, maïs grain, sorgho. Il faut des données thermiques (AquaCrop) pour les autres.
- **Earth Engine** : sans `GEE_PROJECT` (+ `earthengine authenticate` ou compte de service), GPM,
  SMAP, MODIS et le calcul d'indicateurs sont inutilisables.
- **`CAST(... AS JSON)`** dans le collecteur ne marche que sur MySQL, pas sur MariaDB (XAMPP).
- Un calcul d'indicateurs qui échoue n'est pas enregistré (les colonnes `status` / `error_message`
  existent mais ne sont jamais remplies avec un échec).
- Les datasets externes ne sont utilisés nulle part dans le moteur de rotation (choix de l'équipe :
  validation humaine d'abord).

## 5. Test en direct sur ton PC

```bash
cd backend
source venv/Scripts/activate
python scripts/check_data_sources.py            # lecture seule : les 4 API répondent-elles ?
python scripts/check_data_sources.py --store    # + enregistrement dans MySQL
python scripts/check_data_sources.py --gee      # + GPM / SMAP / MODIS (GEE_PROJECT requis)
```

Mise en place du catalogue cultures :

```bash
mysql -u root -p < database/catalogue/001_create_culture.sql
python bd/prepare_culture_csv.py
python bd/connection.py --manifest bd/data/manifest_catalogue_v6.json --csv bd/data/cultures_catalogue_v6.csv
```
