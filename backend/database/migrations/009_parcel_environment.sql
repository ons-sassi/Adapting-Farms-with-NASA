-- Cache des données environnementales d'une parcelle (NASA POWER, SoilGrids, SMAP, GPM, MODIS).
CREATE TABLE IF NOT EXISTS parcel_environment (
    parcelle_id INT NOT NULL,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL,
    data JSON NOT NULL,
    fetched_at DATETIME NOT NULL,
    PRIMARY KEY (parcelle_id),
    CONSTRAINT fk_parcel_environment_parcelle FOREIGN KEY (parcelle_id) REFERENCES parcelles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
