CREATE TABLE external_agri_datasets (
    dataset_id CHAR(36) NOT NULL PRIMARY KEY,
    source_id VARCHAR(100) NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    provider VARCHAR(120) NOT NULL,
    quality_status VARCHAR(40) NOT NULL DEFAULT 'needs_validation',
    retrieved_at DATETIME(6) NOT NULL,
    record_count INT UNSIGNED NOT NULL DEFAULT 0,
    metadata_json JSON NOT NULL,
    records_json JSON NOT NULL,
    raw_json JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_external_agri_source (source_id),
    INDEX idx_external_agri_quality (quality_status),
    INDEX idx_external_agri_retrieved (retrieved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
