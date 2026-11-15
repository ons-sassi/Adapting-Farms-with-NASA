# Patch — Pipeline centralisé des données agricoles externes

Ce patch ajoute la persistance MySQL des datasets externes, conserve les copies JSON brutes/normalisées et ajoute un endpoint de diagnostic.

Voir `database/migrations/README_EXTERNAL_AGRI.md` pour la procédure complète et les limites des sources.

**Important :** le patch ne lance aucune migration, ne collecte aucune donnée à l'installation et ne touche pas à `nasa_challenge`. Il faut d'abord vérifier le `.env` local et l'état des migrations.
