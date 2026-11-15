# Livraison cumulative – finalisation du moteur de rotation

Cette archive est un patch cumulatif à appliquer à la racine du dépôt `adapting-farms-backend`.
Elle reprend les modules de préparation/fusion, explication Groq, snapshots/audit, sous-scores et pondération, puis ajoute les modules de finalisation.

## Installation
1. Sauvegarder le backend.
2. Décompresser l'archive à la racine du dépôt en conservant les chemins.
3. Installer les dépendances : `pip install -r requirements.txt`.
4. Exécuter `database/migrations/005_create_rotation_data_snapshots.sql` si ce n'est pas déjà fait.
5. Exécuter `database/migrations/006_rotation_finalisation.sql`.
6. Redémarrer : `python -m uvicorn app.main:app --reload`.

## Nouvelles routes
- `POST /api/v1/rotation/parcelles/{parcelle_id}/moteur-decision` : calcul des marges à partir de prix, rendements et coûts explicitement fournis. Le score économique normalisé est une convention provisoire et n'est pas présenté comme validé scientifiquement.
- `POST /api/v1/rotation/parcelles/{parcelle_id}/optimiser` : classe jusqu'à trois stratégies candidates déjà générées. Il ne crée pas de nouvelles cultures.
- `POST /api/v1/rotation/parcelles/{parcelle_id}/simuler` : applique uniquement les coefficients de sensibilité explicitement transmis.
- `POST /api/v1/rotation/parcelles/{parcelle_id}/fiabilite` : audite couverture des preuves et validation locale.
- `POST /api/v1/rotation/parcelles/{parcelle_id}/calendrier` : assemble les dates de semis/récolte fournies; ne devine pas les dates manquantes.
- `POST /api/v1/rotation/parcelles/{parcelle_id}/rapport` : export HTML.
- `POST /api/v1/rotation/parcelles/{parcelle_id}/rapport/pdf` : export PDF avec ReportLab.
- `POST /api/v1/rotation/parcelles/{parcelle_id}/retours-conseiller` : enregistre les retours.
- `POST /api/v1/rotation/marche/prix` et `GET /api/v1/rotation/marche/prix` : saisie et consultation d'observations de prix avec source/date/région.
- `POST /api/v1/rotation/donnees/importer` : importe CSV en quarantaine; aucune ligne importée n'est automatiquement utilisée dans un calcul.

## Limites à traiter avant production
- Les sources de prix/rendements/coûts ne sont pas automatiquement collectées par cette livraison. Les données locales doivent être acquises, sourcées et validées.
- Les coefficients de sensibilité climatique/économique doivent être calibrés par culture et région; sans eux, les valeurs ne changent pas dans la simulation.
- L'optimisation classe des stratégies candidates fournies par les moteurs déjà présents. Elle ne remplace pas la génération agronomique complète ni les exclusions.
- Les dates de calendrier viennent des données candidates; une date absente reste absente.
- La fiabilité produite est un audit de couverture documentaire, pas une probabilité statistique de réussite.
- L'import CSV est une zone de quarantaine. La validation de schéma métier, l'approbation admin et les workflows de correction restent à compléter.
- Les caches de données externes et l'administration complète des référentiels ne sont pas implémentés dans ce patch.
- Le score économique utilise une normalisation technique provisoire; à remplacer par une méthode agronomique/économique validée avec l'équipe métier.
- L'export PDF produit un rapport technique basé sur le JSON fourni; la mise en page métier complète et les graphiques restent à faire.

## Vérifications effectuées
- `compileall` sur les fichiers Python du backend : réussi.
- Six tests directs des fonctions de marge, classement, simulation, qualité, calendrier et import CSV : réussis.
- Import complet de `app.main` non vérifié dans l'environnement de génération : le module `python-jose` n'y était pas installé. Installer `requirements.txt` avant la campagne Swagger.
- Migration MySQL, appels externes, authentification et tests HTTP doivent être vérifiés dans l'environnement local.
