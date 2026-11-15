# Configuration : clés, mots de passe et comptes

Tout se règle dans **2 fichiers** (jamais à committer sur Git) :

- `backend/.env` : copie de `backend/.env.example`
- `frontend/.env` : copie de `frontend/.env.example`

Après chaque modification de `backend/.env`, **redémarre uvicorn**. La page **Paramètres** de
l'application affiche ensuite ce qui est configuré (« Configuré » / « À configurer »).

## Résumé

| # | Quoi | Variable(s) dans `backend/.env` | Obligatoire ? | Sert à |
|---|---|---|---|---|
| 1 | MySQL | `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` | **Oui** | Comptes, parcelles, analyses, données collectées |
| 2 | Base du catalogue | `CULTURE_MYSQL_DATABASE` (+ `CULTURE_MYSQL_*` si autre serveur) | Pour les indicateurs | Moteur d'indicateurs (`/indicateurs/...`) |
| 3 | Clé JWT | `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` | **Oui** | Connexion des utilisateurs |
| 4 | Groq | `GROQ_API_KEY`, `GROQ_MODEL` (+ `GROQ_CAPTION_MODEL`) | Pour le chatbot | Compréhension du derja, sous-titres, réponse du chatbot |
| 4b | ElevenLabs | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL` | Non | Réponse vocale du chatbot |
| 5 | Gemini | `GEMINI_API_KEY`, `GEMINI_MODEL` | Non | Lecture des rapports de sol PDF/photo |
| 6 | Google Earth Engine | `GEE_PROJECT` (+ `GEE_SERVICE_ACCOUNT`, `GEE_KEY_FILE`) | Non | Humidité du sol SMAP, pluie GPM, NDVI MODIS, indicateurs |
| 7 | CORS | `CORS_ORIGINS` | Déjà rempli | Autoriser le frontend |

**Sans clé** (rien à configurer, il faut juste Internet) : NASA POWER, ISRIC SoilGrids, World Bank, FAOSTAT.

Dans `frontend/.env` : `VITE_DATA_MODE=api` et `VITE_API_URL=/api/v1` (déjà remplis dans l'exemple).

---

## 1. MySQL (obligatoire)

Ton MySQL 8 local (celui de MySQL Workbench).

```ini
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=agrisense
MYSQL_USER=root
MYSQL_PASSWORD=ton_mot_de_passe_mysql
```

Puis, une seule fois :

```bash
cd backend
python scripts/migrate.py apply --backup-confirmed
```

> L'erreur `Access denied ... (using password: NO)` veut dire que `MYSQL_PASSWORD` est vide.
> Si ta base `agrisense` contient déjà des tables sans la table `schema_migrations`, le script
> refuse : exécute alors à la main dans Workbench les fichiers de `database/migrations/` manquants.

## 2. Catalogue des cultures (base `nasa_challenge`)

Mêmes identifiants que MySQL par défaut. Une seule fois :

```bash
mysql -u root -p < database/catalogue/001_create_culture.sql      # ou l'ouvrir dans Workbench
python bd/prepare_culture_csv.py
python bd/connection.py --manifest bd/data/manifest_catalogue_v6.json --csv bd/data/cultures_catalogue_v6.csv
```

```ini
CULTURE_MYSQL_DATABASE=nasa_challenge
```

## 3. Clé JWT (obligatoire)

Une longue chaîne aléatoire, à générer une fois :

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

```ini
JWT_SECRET_KEY=la_chaine_generee
ACCESS_TOKEN_EXPIRE_MINUTES=720
```

Si tu changes cette clé, tous les utilisateurs devront se reconnecter.

## 4. Groq : chatbot (gratuit avec limites)

1. Va sur https://console.groq.com et crée un compte.
2. Menu **API Keys**, puis **Create API Key**, puis copie la clé (elle commence par `gsk_`).

```ini
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-120b
```

## 4b. ElevenLabs : voix du chatbot (optionnel)

1. Crée un compte sur https://elevenlabs.io.
2. Va dans **Profile → API Keys**, crée une clé et copie-la.
3. Va dans **Voices** et choisis une voix (arabe ou française). Copie son **Voice ID**.

```ini
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
ELEVENLABS_MODEL=eleven_multilingual_v2
```

Pour une réponse plus rapide, mets `ELEVENLABS_MODEL=eleven_flash_v2_5`.
Sans clé, le chatbot répond par écrit seulement.

Sous-titres plus rapides (optionnel) : `GROQ_CAPTION_MODEL=` avec un modèle Groq rapide de ta console.
Laisse-le vide pour utiliser `GROQ_MODEL`.

## 5. Gemini : lecture des rapports de sol

1. Va sur https://aistudio.google.com/apikey et connecte-toi avec un compte Google.
2. Clique **Create API key** et copie la clé.
3. Installe la bibliothèque : `pip install google-genai` (déjà dans `requirements.txt`).

```ini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.6-flash
```

## 6. Google Earth Engine : SMAP, GPM, MODIS

1. Crée (ou choisis) un projet Google Cloud : https://console.cloud.google.com, puis note son **ID**
   (ex. `nasa-challenge-123456`).
2. Inscris ce projet à Earth Engine (usage non commercial / académique, gratuit) :
   https://code.earthengine.google.com/register
3. Dans le projet, active l'API : **APIs & Services → Library → Google Earth Engine API → Enable**.
4. Choisis une méthode de connexion :

**A. Sur ton PC (le plus simple)** : dans le venv du backend, lance

```bash
earthengine authenticate
```

Une page de connexion Google s'ouvre. Ensuite, dans `.env` :

```ini
GEE_PROJECT=id-de-ton-projet
GEE_SERVICE_ACCOUNT=
GEE_KEY_FILE=
```

**B. Sur un serveur (compte de service)** :

1. Va dans **IAM & Admin → Service Accounts → Create**.
2. Donne au compte les rôles **Earth Engine Resource Viewer** et **Service Usage Consumer**.
3. Dans l'onglet **Keys**, choisis **Add key → JSON** et télécharge le fichier.
4. Range ce fichier **hors du dossier du projet**.

```ini
GEE_PROJECT=id-de-ton-projet
GEE_SERVICE_ACCOUNT=nom@id-de-ton-projet.iam.gserviceaccount.com
GEE_KEY_FILE=C:/Users/toi/cles/gee-service-account.json
```

Ne colle jamais le contenu du JSON dans `.env`, et ne l'ajoute jamais à Git.

Vérification : `python scripts/check_data_sources.py --gee`

## 7. CORS

Déjà correct pour le développement (Vite sur le port 5173). Ajoute l'adresse du site si tu le déploies :

```ini
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

---

## Vérifier que tout marche

```bash
cd backend
python scripts/check_data_sources.py           # API externes + catalogue MySQL
python scripts/check_data_sources.py --gee     # + Earth Engine
uvicorn app.main:app --reload                  # puis page Paramètres de l'application
```
