# Rapport d'audit – projet rotation des cultures

Environnement : Python 3.13, pandas 3.0.5, numpy 2.5.3, scipy 1.18.1, pytest 9.1.1. Pas d'accès GEE (aucun identifiant, réseau limité), pas de MySQL.

## 1. Architecture
- `common/connectors.py` : POWER, SoilGrids (REST) ; GPM, SMAP, MODIS, SRTM, MERIT (GEE) ; cache `@cached` ; géométrie GeoJSON.
- `common/indices.py` : fonctions pures (POWER, GPM, sol, SMAP, MODIS, terrain).
- `indicateurs_service/indicateurs.py` : `get_indicateurs()` → blocs `_sol → _power → _gpm → _smap → _modis → _srtm`, chacun isolé.
- `zonal_service/` : données brutes sur polygone + sérialisation JSON. `bd/` : catalogue de cultures MySQL.
- Non utilisé / dupliqué : `test_gpm_monthly_reconstruction.py` (2 copies identiques, appellent GEE à l'import), fichier `=` (résidu de `pip install x>=y`), `.cache_indicateurs/` (pickles).

## 2. Problèmes identifiés
| # | Gravité | Problème | Statut |
|---|---|---|---|
| 1 | Bloquant | `SMAP_ID` / `SMAP_BANDS` non définis → bloc SMAP toujours en erreur | Corrigé (`NASA/SMAP/SPL4SMGP/008`, bandes vérifiées dans le catalogue GEE) |
| 2 | Élevé | Dernier jour GPM (en cours, ex. 8/48 images) rendait NaN CDD/SDII/R20mm/Rx1day de toute la saison | Corrigé (jour exclu de la période + avertissement) |
| 3 | Élevé | Conventions de fin différentes : POWER inclusif, GEE exclusif, `.loc` inclusif | Corrigé : `[start, end[` partout |
| 4 | Élevé | SPI/PCI ignoraient la fin de période (dernier mois disponible) | Corrigé (mois entiers < end) |
| 5 | Élevé | Échec du mensuel (ou des statuts) GPM détruisait les indices journaliers | Corrigé (sous-blocs `gpm.journalier`, `gpm.mensuel`, `gpm.statut_*`) |
| 6 | Moyen | `fetch_gpm_monthly(end=None)` : « aujourd'hui » hors clé de cache ; TTL 7 j pour du provisoire | Corrigé (end résolu avant le cache ; TTL GPM 24 h) |
| 7 | Moyen | SPI : `rolling(k)` compte des lignes ; un mois absent de l'index décalait les cumuls | Corrigé (calendrier mensuel complet) |
| 8 | Moyen | `score_ph(NaN)` = 0.0 ; `rsm_class(NaN)` = « intermédiaire » | Corrigé |
| 9 | Moyen | Source libellée « GPM IMERG V07 (Final) » alors que les données récentes sont `provisional` | Corrigé (libellé neutre, provenance dans `statut_produit`) |
| 10 | Moyen | Indices journaliers : trous de dates / valeurs négatives non détectés | Corrigé (`_daily_complete`) |
| 11 | Moyen | SDII = 0.0 sans jour pluvieux (indéfini, ETCCDI) | Corrigé → NaN (**changement de comportement**) |
| 12 | Faible | Cache : `except Exception: pass` ; pickles non portables entre versions de pandas | Corrigé (exceptions ciblées + avertissement ; version de pandas dans la clé) |
| 13 | Faible | Colonne entièrement vide GEE → dtype object | Corrigé (`_rows_to_df` force float) |
| 14 | Faible | Doublon du code de classification des statuts | Factorisé : `classify_status()` |
| 15 | Faible | POWER : NaN (-999) ignorés silencieusement dans les cumuls | Avertissement ajouté |
| 16 | – | `test_offline.py` périmé (statuts non simulés) | Mis à jour (5 lignes) |

## 3. Vérifications scientifiques
- Demi-heure → jour : mm/h × 0,5 × 48 images ; jour invalide si ≠ 48 images (NaN). Mensuel : mm/h × 24 × jours. Unités IMERG (mm/h) confirmées par le catalogue GEE.
- Sur vos exports réels (35,6815 N / 10,102 E) : jour reconstruit vs mensuel officiel, écart ≤ 1,81 % sur 8 mois comparables ; **juin 2025 : 0,00 mm vs 2,16 mm (cause non établie)**.
- Formules relues : ET0 FAO-56 (Rn, Ra, Rso, gamma, delta), Saxton-Rawls 2006, conversions SoilGrids (`d_factor`), SPI (Gamma + probabilité de zéro, McKee), PCI d'Oliver, échelles MODIS (0,0001 / 0,02 / 0,1).

## 4. Tests créés (`tests/`)
- `test_indices.py` (39) ; `test_connectors_unit.py` (37) ; `test_integration_service.py` (25) ; `test_real_exports.py` (7) ; `test_gee_live.py` (8, ignorés sans `GEE_PROJECT`).
- Les nouveaux tests lancés sur le code d'origine : 40 échecs → ils détectent bien les bugs corrigés.

## 5. Commandes
```
pip install -r requirements.txt
python -m pytest tests -v                 # tests simulés + exports réels
python test_offline.py                    # test de fumée historique (sources simulées, aléatoires)
GEE_PROJECT=mon-projet python -m pytest -m gee -v   # tests réels GEE (après earthengine authenticate)
```
Résultat réel : `108 passed, 8 skipped` (les 8 = GEE réel) ; `test_offline.py` → `ALL OK`.

## 6. Interventions humaines nécessaires
1. **Lancer `pytest -m gee`** avec vos identifiants : jamais exécuté ici.
2. **Politique de couverture GPM** : en strict (actuel), un seul jour incomplet rend les 4 indices NaN. Votre saison blé par défaut (2025-10-15 → 2026-06-12) contient le jour réel incomplet 2026-06-01 (46/48) → CDD/SDII/R20mm/Rx1day indisponibles. Fixer une tolérance (ex. règles ETCCDI/RClimDex, à valider) ou accepter.
3. **Écart juin 2025** (0 vs 2,16 mm) : à expliquer.
4. SDII sans jour pluvieux = NaN : confirmer ce choix.
5. Supprimer les pickles `.cache_indicateurs/` du zip (non portables, et ne jamais désérialiser un cache d'origine inconnue).

## 7. Limitations restantes
- `IMERG_MONTHLY_V07` est vide dès octobre 2025 dans vos exports (catalogue : plus de `permanent` après 2025-09-30, transition vers V8) : SPI/PCI ne couvrent pas les saisons récentes ; le code l'indique par un avertissement. Les données journalières récentes sont `provisional`.
- SPI : référence 2000-06 → dernier mois (~25 ans) < 30 ans recommandés par l'OMM.
- SMAP : moyenne des images 3-horaires disponibles, sans contrôle des 8 images/jour. MODIS/MERIT/SRTM : facteurs d'échelle relus, non exécutés.
- `frost_days`, `heat_stress_days`, `gdd` ignorent les NaN (comptés comme non-événements). `score_ph` est discontinu à la borne de plage (décroissance depuis le pH optimal).
- Convention : `end` de la saison par défaut = date de récolte, donc exclue.
- Code à risque : `main.py`, `zonal_service` et `bd/*` non modifiés ; MySQL non testé.

## 8. Bilan
| Domaine | Verdict |
|---|---|
| Indices climatiques (CDD, SDII, R20mm, Rx1day, SPI, PCI) | VALIDÉ (tests unitaires + référence indépendante pour le SPI) |
| Service `get_indicateurs` (périodes, isolation, JSON, statuts) | VALIDÉ sur sources simulées |
| Conversions GPM, statuts, calendrier | VALIDÉ PARTIELLEMENT (logique locale + exports réels ; requêtes GEE non exécutées) |
| NASA POWER, SoilGrids (appels réseau) | NON TESTABLE ici (conversions testées avec réponses simulées) |
| GEE : GPM, SMAP, MODIS, SRTM, MERIT (requêtes réelles) | NON TESTABLE (pas d'identifiants) |
| MySQL / `bd/` | NON TESTABLE (hors catalogue lu depuis le CSV) |
| Politique de gestion des journées incomplètes ; écart juin 2025 | NON VALIDÉ (décision/investigation humaine) |
