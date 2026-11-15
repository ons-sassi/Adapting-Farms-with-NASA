# État final du backend Adapting Farms

## Bilan

Le backend et les tests hors ligne sont utilisables; la base de données et
l'import réel restent bloqués par MySQL `1045`. Aucun secret n'est reproduit.
Aucune migration, création de base/utilisateur, sauvegarde ou import n'a été
effectué.

## Résultats vérifiés

- Suite de tests : **11 réussis**, aucun échec; un avertissement non bloquant
  Starlette/httpx est émis par `TestClient`.
- Le runner découpe les six migrations et ses deux triggers de snapshots sont
  couverts par tests.
- L'importeur est testé hors ligne avec une base simulée : upsert
  transactionnel, doublons, quarantine, unités, index UNIQUE et rollback.
- La commande de statut des migrations démarre désormais correctement, puis
  échoue à la connexion avec `OperationalError 1045`. Révision actuelle et
  tables réelles : inconnues.
- Les tests de démarrage FastAPI, imports et API smoke test avaient déjà réussi
  lors de la validation précédente; ils n'ont pas été relancés ici.
- Modifications antérieures du moteur de fusion rotation : les entrées
  agriculteur ne sont plus mutées et leur provenance n'est pas marquée
  implicitement comme vérifiée; les tests correspondants sont inclus dans les
  11 tests réussis.

## Données et tables

- Données observées dans les réponses publiques des tests antérieurs : **32**
  (World Bank 25, NASA POWER 2, SoilGrids 5); elles n'ont pas été archivées
  comme dataset ni importées.
- FAOSTAT : délai dépassé, 0 enregistrement.
- GPM/MODIS/SMAP : aucun test, configuration Earth Engine absente.
- Importées : **0**. Tables alimentées : **aucune confirmée**.
- Le CSV local de cultures attendu est absent. L'état des tables MySQL n'est
  pas vérifiable.

## Modifications de cette mission

- Chargement des paramètres `.env` de `bd/` sans écraser les variables
  d'environnement préexistantes; chemin `.env` du backend ancré au projet.
- Ajout du runner SQL avec ledger/checksums, verrou de migration et refus
  d'application non sauvegardée ou sur schéma préexistant non suivi.
- Migration 005 rend la création de sa table réexécutable si la table existe.
- Suppression du chemin `TRUNCATE`; import désormais soumis à manifeste,
  contrat de colonnes/unités, validation de la table et index unique,
  transaction, upsert, journal et quarantine.
- Ajout de tests de sécurité d'import et de parsing des migrations.

## Blocages et intervention requise

1. Renseigner localement `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`,
   `MYSQL_USER`, `MYSQL_PASSWORD`. Pour un catalogue séparé, renseigner aussi
   `CULTURE_MYSQL_HOST`, `CULTURE_MYSQL_PORT`, `CULTURE_MYSQL_DATABASE`,
   `CULTURE_MYSQL_USER`, `CULTURE_MYSQL_PASSWORD` et, si nécessaire,
   `CULTURE_MYSQL_TABLE`. Ne pas envoyer de secrets dans le chat.
2. Faire corriger l'accès MySQL 1045 par l'administrateur autorisé, puis
   vérifier le schéma et la révision existante.
3. Créer et vérifier une sauvegarde avant toute migration; examiner tout objet
   existant non suivi. Aucune migration ne doit être appliquée tant que ces
   vérifications ne sont pas achevées.
4. Fournir un dataset cultures sourcé, son manifeste et confirmer le schéma
   cible ainsi que sa clé unique avant de lancer un import.
5. Configurer `GEE_PROJECT` et l'authentification autorisée pour tester les
   sources Earth Engine; ajouter `GROQ_API_KEY` uniquement si les explications
   textuelles sont souhaitées.

## Vérification finale

Les résultats de test et l'erreur MySQL sont réels. La connexion, la révision
actuelle, l'application des migrations, les volumes importés et les tables
alimentées ne sont **pas** déclarés réussis.
