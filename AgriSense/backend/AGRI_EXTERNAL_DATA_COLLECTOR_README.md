# Données agricoles externes

Ce fichier historique a été remplacé par la documentation maintenue dans
[`database/migrations/README_EXTERNAL_AGRI.md`](database/migrations/README_EXTERNAL_AGRI.md).
Consultez-la pour les routes authentifiées, le stockage MySQL et les copies JSON
`raw/` et `normalized/`, l'import contrôlé CSV/XLSX/JSON, la validation humaine
et les limites de chaque source.

## État des sources

- World Bank, FAOSTAT, NASA POWER et SoilGrids ont des adaptateurs dans le
  collecteur. Leur disponibilité et leurs réponses en direct n'ont pas été
  vérifiées; les tests utilisent des réponses simulées.
- GPM IMERG, SMAP et MODIS s'appuient sur les mécanismes GEE séparés du moteur
  d'indicateurs. La collecte par ce pipeline externe n'est pas activée et le
  statut reste bloqué tant que la configuration GEE nécessaire manque; aucune
  initialisation GEE n'est faite par la collecte externe.
- ONAGRI, DGEDA, EcoCrop, FAO FPMA et World Bank Pink Sheet restent des imports
  documentaires contrôlés. Aucun endpoint non vérifié ni scraping automatique
  n'est configuré.

Pour les réglages optionnels GEE, consultez `.env.example`. Le code charge ces
valeurs via `app.core.config.Settings`; ne placez jamais le contenu d'une clé
privée dans le dépôt ou dans `.env`. Le fichier de clé de compte de service doit
rester local et protégé.

La migration 007 décrit la table requise, mais cette documentation n'applique
aucune migration. Les jeux de données restent `needs_validation` jusqu'à une
revue humaine et ne sont pas injectés automatiquement dans le moteur de
rotation.
