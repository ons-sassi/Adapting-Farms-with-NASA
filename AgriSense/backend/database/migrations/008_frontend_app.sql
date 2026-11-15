-- Données propres à l'interface web (frontend React) :
-- zone agro-écologique et culture actuelle d'une parcelle, analyses de rotation
-- et rotations enregistrées par l'agriculteur.
ALTER TABLE parcelles
    ADD COLUMN zone VARCHAR(120) NULL AFTER slope_percent,
    ADD COLUMN current_crop VARCHAR(120) NULL AFTER zone;

CREATE TABLE IF NOT EXISTS app_analyses (
    id INT NOT NULL AUTO_INCREMENT,
    farmer_id INT NOT NULL,
    parcelle_id INT NOT NULL,
    request JSON NOT NULL,
    result JSON NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_app_analyses_farmer (farmer_id),
    CONSTRAINT fk_app_analyses_user FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_app_analyses_parcelle FOREIGN KEY (parcelle_id) REFERENCES parcelles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS app_saved_rotations (
    id INT NOT NULL AUTO_INCREMENT,
    farmer_id INT NOT NULL,
    analysis_id INT NOT NULL,
    rotation_key VARCHAR(20) NOT NULL,
    rotation JSON NOT NULL,
    saved_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_saved_rotation (analysis_id, rotation_key),
    KEY ix_saved_rotations_farmer (farmer_id),
    CONSTRAINT fk_saved_rotations_user FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_saved_rotations_analysis FOREIGN KEY (analysis_id) REFERENCES app_analyses(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
