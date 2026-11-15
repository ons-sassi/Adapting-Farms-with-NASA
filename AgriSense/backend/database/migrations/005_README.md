# Migration 005 — rotation_data_snapshots

## Objectif
Conserver une photographie versionnée des données fusionnées utilisées pour une génération ou une comparaison de rotations.

## Exécution
Exécuter `005_create_rotation_data_snapshots.sql` une seule fois sur la base MySQL après les migrations créant `users` et `parcelles`.
Les instructions `DELIMITER` et les triggers doivent être exécutés via un client MySQL qui prend en charge cette directive (par exemple le client `mysql`).

## Immutabilité
Les routes applicatives exposent uniquement la création, la liste et la lecture. Les triggers bloquent également les opérations SQL `UPDATE` et `DELETE` sur les snapshots. La suppression d'une parcelle ou d'un utilisateur référencé entraîne toutefois la suppression en cascade : si la conservation légale/historique doit survivre à ces suppressions, il faudra remplacer ces cascades par une politique d'archivage avant production.

## Retour arrière
La suppression de la table et des triggers détruit l'historique ; ne pas l'exécuter en production sans export/backup préalable.
