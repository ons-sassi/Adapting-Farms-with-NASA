# Audit MySQL et migrations

## Résultat de connexion

La vérification en lecture seule `python scripts/migrate.py status` échoue avec
MySQL `1045` (`OperationalError`, authentification refusée). Les tentatives
précédentes sur les connexions backend et catalogue cultures ont le même
résultat. Le port répond, mais l'accès au schéma n'est pas établi.

Aucun secret n'est affiché ici. Sans fichier `.env` ni surcharge
d'environnement, les valeurs par défaut sont :

| Connexion | Hôte/port | Base | Identifiant | Mot de passe |
|---|---|---|---|---|
| Backend SQLAlchemy | `127.0.0.1:3306` | `agrisense` | `root` | vide |
| Catalogue `bd/` | `localhost:3306` | `nasa_challenge` | `root` | vide |

Le backend lit `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER` et
`MYSQL_PASSWORD`. Le catalogue cultures utilise les surcharges
`CULTURE_MYSQL_HOST`, `CULTURE_MYSQL_PORT`, `CULTURE_MYSQL_DATABASE`,
`CULTURE_MYSQL_USER`, `CULTURE_MYSQL_PASSWORD` et `CULTURE_MYSQL_TABLE`.
Pour le catalogue, base et table ne retombent pas sur `MYSQL_DATABASE` et
`MYSQL_TABLE`; elles ont leurs propres valeurs par défaut. Renseigner les
identifiants autorisés localement dans `.env`, vérifier les droits et ne pas
transmettre le mot de passe dans le dépôt ou le rapport. Aucun utilisateur ou
schéma n'a été créé.

## Ordre et état des migrations

Les scripts existants sont `001_create_users.sql`,
`002_create_parcelles.sql`, `003_create_sol.sql`,
`004_create_indicateurs.sql`, `005_create_rotation_data_snapshots.sql` et
`006_rotation_finalisation.sql`. Leur ordre repose sur les dépendances
`users` → `parcelles` → sol/indicateurs/snapshots et tables finales.

La révision effectivement appliquée et les tables présentes restent
**inconnues** : l'erreur 1045 a empêché toute lecture de `information_schema`.
Aucune migration n'a été lancée et aucune sauvegarde n'a été créée ou vérifiée.
Alembic ne dispose pas d'une configuration complète (`alembic.ini`, `env.py`
et révisions); le projet garde ses migrations SQL.

Le nouveau `scripts/migrate.py` ajoute un ledger `schema_migrations`, des
checksums, un verrou consultatif et une commande `status`. `apply` exige
explicitement `--backup-confirmed`, ne crée ni base ni utilisateur, et refuse
d'appliquer une baseline sur un schéma non vide non suivi. Les migrations DDL
MySQL ne sont pas transactionnelles : une interruption partielle demande une
inspection et une reprise manuelle. Les migrations déjà consignées sont
ignorées si leur checksum correspond.

Migration 005 rend la création de sa table `IF NOT EXISTS`; ses triggers n'ont
pas de création conditionnelle. Un état partiel ou des objets préexistants non
consignés sont refusés par le runner plutôt que réparés automatiquement.
Migration 006 utilise également `CREATE TABLE IF NOT EXISTS`.

## Écarts connus modèle / SQL

- `RotationSnapshot` déclare `ON DELETE CASCADE` vers `parcelles` et `users`,
  alors que les clés étrangères de migration 005 ne précisent pas cette
  cascade.
- Les tables d'import, de retours conseiller et de prix de marché de la
  migration 006 sont définies en SQL; leur présence réelle n'a pas pu être
  vérifiée.
- Les migrations SQL 001–004 utilisent `CREATE TABLE IF NOT EXISTS`; cela
  évite une erreur sur table existante mais ne garantit pas la compatibilité
  des colonnes ni une reprise sûre d'une migration partielle.

## Conditions avant application

1. Renseigner les variables d'environnement nécessaires et obtenir une
   connexion autorisée.
2. Examiner l'état actuel du schéma et résoudre l'erreur 1045.
3. Créer et vérifier une sauvegarde exploitable.
4. Exécuter `python scripts/migrate.py status`, examiner les objets non suivis,
   puis seulement décider d'une application avec autorisation explicite.

Ni `status` n'a pu lire la révision actuelle, ni `apply` n'a été exécuté.
