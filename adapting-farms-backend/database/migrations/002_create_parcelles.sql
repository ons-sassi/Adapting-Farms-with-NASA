-- À exécuter dans la base MySQL déjà utilisée par le backend.
-- La table users doit exister avant cette migration.
CREATE TABLE IF NOT EXISTS parcelles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    farmer_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    description TEXT NULL,
    area_ha FLOAT NOT NULL,
    latitude FLOAT NULL,
    longitude FLOAT NULL,
    geometry JSON NULL,
    irrigation_type VARCHAR(40) NOT NULL DEFAULT 'none',
    water_source VARCHAR(100) NULL,
    slope_percent FLOAT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_parcelles_farmer_id (farmer_id),
    CONSTRAINT fk_parcelles_farmer FOREIGN KEY (farmer_id)
        REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS parcelle_cultures (
    id INT AUTO_INCREMENT PRIMARY KEY,
    parcelle_id INT NOT NULL,
    crop_name VARCHAR(120) NOT NULL,
    season VARCHAR(40) NOT NULL,
    notes TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_parcelle_cultures_parcelle_id (parcelle_id),
    CONSTRAINT fk_parcelle_cultures_parcelle FOREIGN KEY (parcelle_id)
        REFERENCES parcelles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS parcelle_constraints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    parcelle_id INT NOT NULL,
    constraint_type VARCHAR(80) NOT NULL,
    description TEXT NOT NULL,
    INDEX ix_parcelle_constraints_parcelle_id (parcelle_id),
    CONSTRAINT fk_parcelle_constraints_parcelle FOREIGN KEY (parcelle_id)
        REFERENCES parcelles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
