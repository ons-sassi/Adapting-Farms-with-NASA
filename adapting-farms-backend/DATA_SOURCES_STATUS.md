# État des sources de données

## Collecteurs et essais d'accès

| Source | Format / usage | Essai observé | Limites et statut |
|---|---|---|---|
| World Bank | API publique JSON; indicateurs nationaux | 25 enregistrements retournés lors d'un test précédent | Réponse consultée, non sauvegardée et non importée; l'indicateur exact et les statistiques de qualité ne sont pas conservés |
| NASA POWER | API publique JSON/CSV; climat ponctuel | 2 lignes retournées lors d'un test précédent | Réponse consultée, non persistée; pas d'import MySQL |
| SoilGrids (ISRIC) | API publique JSON; propriétés et profondeurs de sol | 5 valeurs de profondeur retournées lors d'un test précédent | Réponse consultée, non persistée; données estimatives, à distinguer d'une analyse agriculteur/laboratoire |
| FAOSTAT | API/dataset FAO | Requête de test expirée | Aucun enregistrement collecté |
| GPM, MODIS, SMAP | Collections Google Earth Engine utilisées par `common/connectors.py` | Pas de test réel | Projet/identifiants Earth Engine requis; `GEE_PROJECT` n'est pas configuré |
| Catalogue cultures local | CSV attendu par `bd/connection.py` | Fichier absent | Aucun enregistrement importable trouvé |
| Groq | API de génération d'explications | Pas de test réel | `GROQ_API_KEY` absente; optionnel pour texte seulement, pas pour calculs ou décisions |

Les 25 + 2 + 5 observations sont des tailles de réponses de tests antérieurs,
pas des données conservées comme datasets. Aucun scraping supplémentaire n'a
été exécuté pour ce rapport. Aucun de ces enregistrements n'a été importé :
**0 enregistrement persistant**.

## Fichiers locaux

Aucun CSV, JSON ou Excel agricole n'a été trouvé dans les emplacements de
datasets examinés (`data/external_agri/` et `bd/data/`). Le chemin attendu
`bd/data/cultures_completes_8_especes_v6.csv` n'existe pas. Aucun relevé local
de date de collecte, de colonnes ou de licence n'est donc disponible pour ces
sources.

## Implémentation existante

- Les connecteurs actifs NASA POWER et SoilGrids, ainsi que GPM/MODIS/SMAP,
  se trouvent principalement dans `common/connectors.py`.
- `app/integrations/nasa/power_client.py` et
  `app/integrations/soilgrids/client.py` sont des stubs.
- NASA POWER et SoilGrids peuvent être sollicités sans identifiant selon le
  connecteur; GPM/MODIS/SMAP exigent l'initialisation Earth Engine.
- Le contrôle de qualité quantitatif des réponses (doublons, valeurs
  manquantes, unités et aberrants) n'a pas été calculé sur un dataset archivé.
  Les réponses de test ne sont pas disponibles pour refaire cet audit.

## Provenance et priorité

Ne pas assimiler une estimation SoilGrids à une mesure du fermier. Conserver
la source, la référence d'origine, la date, la méthode, les unités et la
version au niveau du lot; ne remplacer aucune observation du fermier. Les
prix, rendements, calendriers et besoins agronomiques ne doivent pas être
complétés par des valeurs fabriquées. Les calculs de score doivent rester
indépendants de Groq.
