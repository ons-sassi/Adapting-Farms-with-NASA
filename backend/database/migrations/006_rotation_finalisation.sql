-- MySQL 8+ : tables d'import en quarantaine et retours conseiller.
CREATE TABLE IF NOT EXISTS rotation_import_batches (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 user_id INT NOT NULL,
 dataset VARCHAR(40) NOT NULL,
 row_count INT NOT NULL,
 payload_json JSON NOT NULL,
 status VARCHAR(24) NOT NULL DEFAULT 'PENDING_REVIEW',
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_rotation_import_user (user_id),
 CONSTRAINT fk_rotation_import_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS rotation_advisor_feedback (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 parcel_id INT NOT NULL,
 user_id INT NOT NULL,
 recommendation_id VARCHAR(100) NOT NULL,
 rating TINYINT NOT NULL,
 comment TEXT NULL,
 accepted BOOLEAN NULL,
 adjustments_json JSON NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_rotation_feedback_parcel (parcel_id),
 INDEX idx_rotation_feedback_recommendation (recommendation_id),
 CONSTRAINT fk_rotation_feedback_parcel FOREIGN KEY (parcel_id) REFERENCES parcelles(id) ON DELETE CASCADE,
 CONSTRAINT fk_rotation_feedback_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT chk_rotation_feedback_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS rotation_market_prices (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 user_id INT NOT NULL,
 crop VARCHAR(120) NOT NULL,
 region VARCHAR(120) NOT NULL,
 price_per_t DECIMAL(14,3) NOT NULL,
 currency VARCHAR(8) NOT NULL,
 source VARCHAR(255) NOT NULL,
 observed_at DATETIME NOT NULL,
 metadata_json JSON NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_rotation_market_crop_region_date (crop,region,observed_at),
 CONSTRAINT fk_rotation_market_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;
