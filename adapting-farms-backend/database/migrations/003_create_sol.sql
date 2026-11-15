CREATE TABLE IF NOT EXISTS soil_analyses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    parcelle_id INT NOT NULL,
    ph FLOAT NULL,
    organic_matter_percent FLOAT NULL,
    texture VARCHAR(100) NULL,
    nitrogen_mg_kg FLOAT NULL,
    phosphorus_mg_kg FLOAT NULL,
    potassium_mg_kg FLOAT NULL,
    salinity_ds_m FLOAT NULL,
    limestone_percent FLOAT NULL,
    cec_cmol_kg FLOAT NULL,
    sampled_at DATE NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'manual',
    notes TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_soil_analyses_parcelle_id (parcelle_id),
    CONSTRAINT fk_soil_analyses_parcelle
        FOREIGN KEY (parcelle_id) REFERENCES parcelles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
