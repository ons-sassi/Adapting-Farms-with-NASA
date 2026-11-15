# Rotation - API de scoring agronomique

## Endpoint
`POST /api/v1/rotation/parcelles/{parcelle_id}/scoring`

Authentification JWT requise. La parcelle doit appartenir à l'utilisateur connecté.

## Principe
Cette API agrège six sous-scores normalisés entre 0 et 1 :
- `eau`
- `climat_thermique`
- `fertilite_sol`
- `protection_erosion`
- `dynamique_vegetative`
- `compatibilite_succession`

Les sous-scores sont fournis par le client ou par les moteurs spécialisés. Cette API
n'invente pas les formules sources manquantes et ne lance pas les traitements satellite,
climat ou sol. Une valeur `null` est ignorée et sa pondération est redistribuée entre
les dimensions disponibles. Les dimensions manquantes restent explicitement signalées.

## Exemple de corps JSON
```json
{
  "rotations": [
    {
      "identifiant": "rotation_A",
      "cultures": ["pois chiche", "blé dur", "tournesol"],
      "sous_scores": {
        "eau": 0.82,
        "climat_thermique": 0.76,
        "fertilite_sol": null,
        "protection_erosion": 0.90,
        "dynamique_vegetative": 0.71,
        "compatibilite_succession": 0.85
      },
      "preuves": {
        "eau": ["NASA POWER: dataset/version/date"],
        "dynamique_vegetative": ["Sentinel-2: période et méthode"]
      },
      "commentaires": ["Fertilité du sol non évaluée faute de mesures."]
    }
  ],
  "ponderations": {
    "eau": 1,
    "climat_thermique": 1,
    "fertilite_sol": 1,
    "protection_erosion": 1,
    "dynamique_vegetative": 1,
    "compatibilite_succession": 1
  },
  "minimum_dimensions_requises": 3
}
```

## Installation
Installer les dépendances depuis `requirements.txt`, puis démarrer :
`python -m uvicorn app.main:app --reload`

## Archive nettoyée
Le ZIP distribué ne contient pas les environnements virtuels, caches Python, fichiers
`.pyc`, secrets `.env`, ni la copie imbriquée du même projet. Recréer l'environnement
local avec `python -m venv .venv` puis `pip install -r requirements.txt`.
