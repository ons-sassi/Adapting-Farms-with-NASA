# AgriSense — interface (React + Vite)

```bash
cd views
npm install
npm run dev        # http://localhost:5173
```

Configuration (`views/.env`, modèle `.env.example`) : `VITE_DATA_MODE=demo` (données statiques) ou `api` (FastAPI, `VITE_API_URL`).

## État des fonctionnalités

| Fonctionnalité | État |
|---|---|
| Navigation, sidebar, design responsive | Opérationnel |
| Carte satellite Leaflet, dessin et modification de polygones (Geoman), calcul de surface | Opérationnel |
| Import GeoJSON des limites de parcelle | Opérationnel |
| Import PDF de rapport de sol | Fichier joint seulement (lecture automatique non disponible) |
| Création / modification / suppression de parcelles | Opérationnel en mode démo (stockage local du navigateur) |
| Choix des cultures, priorités, contraintes, récapitulatif | Opérationnel (interface) |
| Analyse, rotations, scores, 4 indices composites | **Simulé** : résultat de démonstration fixe, aucun calcul |
| Enregistrement de rotation, export CSV / JSON, rapport imprimable | Opérationnel (sur les données affichées) |
| Chatbot | **Simulé** : réponses d'exemple pour les questions suggérées |
| Données NASA, SoilGrids, catalogue serveur | Non connecté |

Toutes les données de démonstration sont dans `src/data/demo/demoData.js` ; tous les appels passent par `src/api/client.js` (chemins FastAPI déjà prévus).
