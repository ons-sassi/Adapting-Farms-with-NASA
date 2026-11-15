-- Migration 005 : snapshots versionnés des données utilisées par la rotation.
-- Précondition : tables users et parcelles existantes ; MySQL 8+ recommandé.
-- Les snapshots sont append-only. Les triggers empêchent UPDATE et DELETE.

CREATE TABLE IF NOT EXISTS rotation_data_snapshots (
    id INT NOT NULL AUTO_INCREMENT,
    parcelle_id INT NOT NULL,
    farmer_id INT NOT NULL,
    version INT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    payload JSON NOT NULL,
    source_metadata JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_rotation_snapshot_parcelle_version UNIQUE (parcelle_id, version),
    CONSTRAINT fk_rotation_snapshot_parcelle FOREIGN KEY (parcelle_id)
        REFERENCES parcelles(id),
    CONSTRAINT fk_rotation_snapshot_farmer FOREIGN KEY (farmer_id)
        REFERENCES users(id),
    INDEX ix_rotation_snapshot_farmer (farmer_id),
    INDEX ix_rotation_snapshot_hash (content_hash),
    INDEX ix_rotation_snapshot_parcelle_created (parcelle_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DELIMITER $$
CREATE TRIGGER trg_rotation_snapshots_no_update
BEFORE UPDATE ON rotation_data_snapshots
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Rotation snapshots are immutable';
END$$

CREATE TRIGGER trg_rotation_snapshots_no_delete
BEFORE DELETE ON rotation_data_snapshots
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Rotation snapshots are immutable';
END$$
DELIMITER ;
