# Explications agricoles avec Groq

## Architecture et limites

Les moteurs Python existants restent les seuls producteurs des séquences,
scores et classements. Groq n'est appelé qu'après réception de résultats
calculés; son client ne reçoit que le JSON fourni, sans session, accès SQL ni
outil. Les explications ne remplacent pas les résultats métier et ne les
réécrivent pas dans la base.

Le service réutilise le client officiel asynchrone `groq.AsyncGroq`, demande
une réponse JSON Schema stricte et valide à nouveau la réponse avec Pydantic.
Les recommandations doivent citer au moins un JSON Pointer vers une valeur
présente et non vide dans les données reçues. Les contenus libres restent des
productions LLM : ils doivent être relus comme des explications, pas comme une
validation scientifique indépendante.

Le prompt traite les chaînes fournies comme des données non fiables et rejette
explicitement les consignes éventuellement intégrées aux données. Le corps est
limité à `GROQ_MAX_INPUT_CHARS`. Aucun message, résultat agricole, jeton ou
secret n'est journalisé.

## Installation et variables

Depuis la racine du backend, dans l'environnement virtuel :

```powershell
python -m pip install -r requirements.txt
```

Configurer les variables dans le `.env` local (ne pas committer ce fichier) :

```dotenv
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
GROQ_TIMEOUT=30
GROQ_MAX_COMPLETION_TOKENS=1800
GROQ_MAX_INPUT_CHARS=30000
```

`GROQ_TIMEOUT_SECONDS` est aussi accepté pour compatibilité. Le modèle
`openai/gpt-oss-120b` figure au catalogue officiel Groq consulté le 15 novembre
2026 et prend en charge les sorties JSON Schema strictes. Aucun appel réel au
fournisseur n'a été exécuté dans le cadre de ce patch; la clé doit être fournie
et autorisée avant utilisation. Références : [catalogue des modèles Groq](https://console.groq.com/docs/models)
et [sorties structurées JSON Schema](https://console.groq.com/docs/structured-outputs).

## Routes

Les routes de génération exigent le JWT fermier habituel. Le endpoint santé
n'effectue aucun appel distant et ne confirme que la présence de la clé.

| Méthode et route | Fonction |
|---|---|
| `POST /api/v1/explanations/generate` | Explication générale de résultats calculés |
| `POST /api/v1/explanations/rotation` | Stratégies de rotation et compromis |
| `POST /api/v1/explanations/scoring` | Explication des scores transmis; champs absents laissés indisponibles |
| `POST /api/v1/explanations/risks` | Risques, estimations, incertitudes et données manquantes |
| `GET /api/v1/explanations/health` | État de configuration local, sans requête Groq |
| `POST /api/v1/rotation/parcelles/{parcelle_id}/expliquer` | Route existante conservée, servie par le nouveau service |

Schéma de requête dans Swagger :

```json
{
  "results": {
    "<sortie_du_moteur>": "Remplacer par les résultats réels, inchangés."
  },
  "language": "fr",
  "detail": "detailed"
}
```

La réponse structurée contient `summary`, `agronomic_analysis`,
`economic_analysis`, `water_analysis`, `climate_risks`, `advantages`,
`disadvantages`, `recommendations` et `limitations`. Chaque recommandation
contient du texte et ses pointeurs `evidence`. Les métadonnées comprennent le
modèle, la date de génération, la langue, la catégorie et l'empreinte SHA-256
des résultats transmis.

Erreurs documentées dans Swagger : `401` (authentification), `413` (entrée
trop grande), `422` (requête invalide), `502` (réponse ou service fournisseur
invalide), `503` (clé absente ou limite Groq) et `504` (timeout). Les erreurs
ne contiennent ni la clé, ni le corps de réponse fournisseur.

## Validation

Les tests utilisent un client Groq simulé; aucun secret ni compte réel n'est
requis. Ils couvrent l'absence de clé, la réussite, les erreurs fournisseur,
le timeout, les réponses invalides, les champs de score absents, trois
stratégies, le français, l'arabe, les recommandations non étayées et
l'immutabilité des entrées. Le test réel de la clé et de la disponibilité du
compte n'est pas effectué automatiquement.
