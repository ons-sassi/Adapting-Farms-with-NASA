CREATE TABLE IF NOT EXISTS indicateur_calculations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  parcelle_id INT NOT NULL,
  farmer_id INT NOT NULL,
  culture VARCHAR(160) NOT NULL,
  start_date VARCHAR(10) NULL,
  end_date VARCHAR(10) NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'completed',
  result JSON NULL,
  error_message VARCHAR(2000) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_ind_calc_parcelle_created (parcelle_id, created_at),
  INDEX ix_ind_calc_farmer (farmer_id),
  CONSTRAINT fk_ind_calc_parcelle FOREIGN KEY (parcelle_id) REFERENCES parcelles(id) ON DELETE CASCADE,
  CONSTRAINT fk_ind_calc_farmer FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
