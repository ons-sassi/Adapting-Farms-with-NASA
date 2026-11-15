# AgriSense — Adapting Farms with NASA

Application complète : interface React (`frontend/`) reliée au backend FastAPI (`backend/`).

```
AgriSense/
├── backend/    FastAPI + MySQL (auth JWT, parcelles, moteur de rotation, Groq, Gemini)
│   ├── app/api/v1/frontend_bridge.py   ← routes utilisées par l'interface
│   ├── app/services/frontend_catalog.py, frontend_analysis_service.py
│   ├── data/catalog/                   ← catalogue cultures + calendrier FAO Tunisie
│   └── database/migrations/008_frontend_app.sql
└── frontend/   React + Vite (ancien dossier views/)
```

## Comment les deux parties sont reliées

| Interface (client.js)              | Backend (`/api/v1/...`)                 |
|------------------------------------|-----------------------------------------|
| Connexion / inscription            | `/auth/login`, `/auth/register` (JWT)   |
| Mes terrains                       | `/farms`, `/parcels` (table `parcelles` + pH dans `soil_analyses`) |
| Choix des cultures                 | `/crops` (catalogue CSV, 41 cultures)   |
| Analyse → Résultats                | `POST /analyses` → règles d'exclusion + générateur de séquences + pondération des priorités |
| Rotations enregistrées             | `/analyses/{id}/saved-rotations`, `/saved-rotations` |
| Chatbot (voix derja, sous-titres, impact) | `/chatbot/message`, `/chatbot/captions`, `/chatbot/speak` (Groq + ElevenLabs) |
| Calculateur d'impact (eau, azote, CO2) | `/impact/calculer` |
| Import d'un rapport de sol PDF     | `/documents/extract` (Gemini, clé `GEMINI_API_KEY`) |
| Climat, sol, humidité d'une parcelle | `/parcels/{id}/environment` (NASA POWER, SoilGrids ; SMAP/GPM/MODIS si Earth Engine) |
| Page Paramètres / Accueil          | `/status` (services configurés, sans jamais renvoyer de secret) |

En développement, Vite redirige `/api` vers `http://127.0.0.1:8000` (voir `frontend/vite.config.js`) : pas de souci de CORS.

## Clés et mots de passe

Voir **CONFIGURATION.md** : MySQL, JWT, Groq, Gemini, Google Earth Engine (ce qui est obligatoire ou non, et où l'obtenir).

## Lancer le projet (Git Bash sous Windows)

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env        # puis remplir MYSQL_* et JWT_SECRET_KEY
python scripts/migrate.py status
python scripts/migrate.py apply --backup-confirmed   # base vide ou déjà suivie par le journal
uvicorn app.main:app --reload
```

Vérifier : http://127.0.0.1:8000/docs

> Base existante : si ta base a déjà les tables 001–007 **sans** la table `schema_migrations`,
> le script refuse d'appliquer (sécurité). Dans ce cas, fais une sauvegarde puis exécute
> seulement `database/migrations/008_frontend_app.sql` dans MySQL Workbench.

### 2. Frontend

```bash
cd frontend
cp .env.example .env        # VITE_DATA_MODE=api
npm install
npm run dev
```

Ouvrir http://localhost:5173 → créer un compte → « Nouvelle parcelle ».

Mode sans serveur : `VITE_DATA_MODE=demo` dans `frontend/.env`.

## À savoir

- Les scores eau et climat utilisent le climat réel de la parcelle (NASA POWER : pluie, ET0, degrés-jours)
  et le pH SoilGrids si aucune analyse de sol n'est saisie. Sans Internet côté serveur, ils sont estimés
  à partir du catalogue (indiqué dans les résultats).
  La compatibilité de succession vient du vrai moteur du backend.
- Horizon de rotation : 3 ou 4 ans (limite du moteur).
- Correction faite dans `app/engine/rotation/sequence_generator.py` : la date de récolte était une
  chaîne et faisait planter la génération dès la 2e année.
- Tests : `cd backend && pytest`.
