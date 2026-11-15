# Audit du pipeline d'importation agricole

## État préalable

Aucune importation réelle n'a été lancée : la base MySQL refuse
l'authentification (1045), son schéma et ses index ne peuvent donc pas être
validés. Le fichier attendu
`bd/data/cultures_completes_8_especes_v6.csv` est absent. Aucun dataset
agricole n'a été trouvé sous `data/external_agri/` ou `bd/data/`. Résultat :
**0 ligne importée, 0 table alimentée**.

## Changements de sécurité apportés

`bd/mysql_ingestor.py` a été remplacé par un pipeline à contrat explicite :

- archive les octets source sous `data/external_agri/raw/imports/` avec SHA-256;
- exige un manifeste contenant source, référence, date ISO de collecte,
  méthode, version du dataset et unités;
- normalise les noms de colonnes, valide colonnes autorisées/obligatoires,
  nombres finis, types entiers/booléens et unités attendues;
- ignore les doublons exacts du même lot et met en quarantaine les lignes
  invalides ou les clés métier contradictoires;
- exige une table existante InnoDB et un index `UNIQUE` correspondant
  exactement à la clé déclarée; n'ajoute pas de table, colonne ou index;
- effectue des `INSERT ... ON DUPLICATE KEY UPDATE` dans une transaction;
  toute erreur d'écriture annule le lot;
- écrit un journal de lot et de ligne, avec compteurs insérés, mis à jour,
  ignorés, rejetés et mis en quarantaine.

L'option `truncate` a été retirée. Le code `bd/` ne contient plus d'appel
`TRUNCATE`, et l'ingesteur n'exécute pas de DDL. Les données brutes archivées
ne sont pas modifiées. La provenance du lot est conservée dans le journal; le
hash et le numéro de ligne relient les résultats au fichier source.

`bd/connection.py` exige maintenant `--manifest`; il ne lance aucun import
implicitement. Le contrat du catalogue est limité aux colonnes attendues par
ce consommateur, avec unités explicites pour les mesures. Les seuils
agronomiques non documentés ne sont pas inventés.

## Utilisation future (non exécutée)

Préparer un manifeste JSON vérifiable avec `source`,
`source_reference`, `collected_at`, `method`, `dataset_version` et `units`,
puis lancer le script uniquement après validation du schéma et de l'accès :

```powershell
python bd\connection.py --manifest chemin\vers\manifest.json
```

Le manifeste ne remplace ni les identifiants MySQL ni une validation des
droits. Aucun import, upsert ou archivage de dataset réel n'a eu lieu durant
cette mission.

## Validation automatisée

Les tests hors ligne couvrent l'upsert avec une clé unique, l'archivage brut,
les doublons identiques et contradictoires, le rejet d'unités incompatibles,
le blocage sans index unique et le rollback d'une erreur simulée. Ils
n'établissent pas l'état réel de la base MySQL.
