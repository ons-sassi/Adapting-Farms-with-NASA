# Modules ajoutés : Chatbot + Impact Calculator

Principe : le cœur ne dépend d'aucun des deux. Le chatbot est un adaptateur ; l'impact est un moteur du cœur.

```
Navigateur : page /chatbot/live (étape 1 : sous-titrage direct)  --texte-->  app/api/chatbot.py -> services/chatbot/ (NLU + orchestrateur)
                                                          |
                                         services/context_builder.py  (contexte de décision unique)
                                          |- parcelle / sol / indicateurs   (services existants)
                                          |- engine/rotation                (moteur existant)
                                          '- services/impact_service.py -> engine/impact/   <- CŒUR
                                                          |
                                         llm/explanation_service.py (Groq reformule, ne calcule pas)
                                                          |
                                         POST /chatbot/speak -> tts.py (étape 3 : ElevenLabs, côté serveur)
```

## Fichiers ajoutés (à copier à la racine du dépôt)
| Fichier | Rôle |
|---|---|
| app/engine/impact/ | Calculateur d'impact (impact.py d'origine + impact_params.json) |
| app/engine/rotation/lite_rules.py + rotation_rules.json | decision.py d'origine : mode « lite » sans parcelle uniquement |
| app/services/impact_service.py | Service d'impact (utilisable seul) |
| app/services/context_builder.py | Contexte de décision, enrichi avec l'impact |
| app/services/chatbot/{nlu,orchestrator,factory,assets}.py + data/ | Chatbot (nlu = llm.py sans client LLM propre) |
| app/api/impact.py, app/api/chatbot.py | Endpoints |
| app/services/chatbot/{captions,tts}.py + static/live.html | Étape 1 (sous-titrage direct) et étape 3 (ElevenLabs). Plus aucun Streamlit |
| tests/test_*.py, requirements-chatbot.txt | Tests (22) et dépendances |

## Branchements dans le code existant (5 modifications)
1. **app/core/config.py** : ajouter `CHATBOT_ENABLED: bool = False` et `IMPACT_ENABLED: bool = True`.
2. **app/api/router.py** :
   ```python
   from app.api import impact
   api_router.include_router(impact.router, prefix="/impact", tags=["impact"])
   if settings.CHATBOT_ENABLED:
       from app.api import chatbot
       api_router.include_router(chatbot.router, prefix="/chatbot", tags=["chatbot"])
   ```
3. **app/api/chatbot.py** : remplacer les 3 stubs `get_current_user`, `get_db`, `get_chatbot` (ils échouent volontairement tant qu'ils ne sont pas branchés : pas d'accès anonyme par oubli). `get_chatbot` = `factory.build_chatbot(...)` construit une fois (adaptateurs sur parcelle_service, sol_service, indicateur_service, pipeline rotation ; `llm_json` et `llm_text` = groq_client ; `explainer` = explanation_service).
4. **api/rotation_finalisation.py** (impact dans le flux normal, sans chatbot) :
   `ImpactService(id_map=...).enrich_ranking(rotations, hectares=parcelle.surface, n_rate=...)` : ajoute `rotation["impact"]`, ne modifie aucun score.
5. **llm/explanation_service.py / prompts.py** : ajouter `ImpactService.prompt_block(ctx.impact)` au prompt ; le texte du LLM n'a pas le droit de produire d'autres chiffres.

## Chatbot vocal : étapes 1 et 3
- **Étape 1 (sous-titrage direct)** : `GET /api/v1/chatbot/live`. La reconnaissance vocale tourne dans le navigateur (Chrome ou Edge, Internet requis) ; chaque phrase est traduite en anglais par `POST /chatbot/captions`, puis envoyée à `POST /chatbot/message`. Coller le token JWT dans la page.
- **Étape 3 (ElevenLabs)** : `POST /chatbot/speak` renvoie du MP3. Variables `.env` : `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL` (défaut `eleven_multilingual_v2` ; `eleven_flash_v2_5` pour moins de latence).
- Les modèles ElevenLabs gèrent l'arabe et le français, sans modèle dédié au derja tunisien : tester la voix avec de vraies réponses. La réponse du chatbot est en français ou en anglais (`lang`) ; les chiffres d'impact restent affichés à l'écran et ne sont pas lus.

## Limites connues
- Impact chiffré pour blé et fève seulement ; autres cultures -> `available: false` (jamais de chiffre inventé).
- Dose d'azote = 100 kg N/ha d'EXEMPLE tant que `n_rate` n'est pas fourni (signalé dans `needs_info`).
- Valeurs de impact_params.json et poids de rotation_rules.json : à valider par l'agronome.
- IDs de cultures : `crops.json` du chatbot vs catalogue `bd/cultures.py` -> utiliser `id_map`.
- Les signatures des services du cœur sont supposées (marquées `# ADAPT`).
