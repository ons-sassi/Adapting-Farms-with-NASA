# Database – Adapting Farms

## Présentation
Dossier des scripts SQL et ressources de la base MySQL 8+ du projet Adapting Farms.
La structure existante doit être conservée et améliorée progressivement.

## Organisation
- `init.sql` : schéma initial.
- `migrations/` : évolutions SQL validées.
- `diagnostics/` : contrôles non destructifs.
- `seeds/` : données de référence.
- `views/` : définitions des vues SQL.
- `backups/` : sauvegardes locales.

## Installation
Pour une nouvelle installation : créer la base MySQL, exécuter `init.sql`, charger les données de référence validées, puis configurer la connexion FastAPI.

Pour une base existante : sauvegarder la base, exécuter les diagnostics, examiner les résultats et appliquer uniquement les migrations validées.

## Règles
- Ne pas supprimer ni remplacer les données existantes sans validation.
- Numéroter les migrations et les tester avant application.
- Conserver la source, la période, les unités et la provenance des données satellitaires.
- Ne pas versionner les sauvegardes contenant des données réelles.

## Statut
Les migrations et seeds sont des emplacements d'organisation à compléter après audit. Ne pas exécuter de fichier vide ou non validé.
