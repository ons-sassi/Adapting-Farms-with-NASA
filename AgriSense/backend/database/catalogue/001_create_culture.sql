-- Table du catalogue des cultures lue par bd/cultures.py (moteur d'indicateurs).
-- À exécuter dans la base CULTURE_MYSQL_DATABASE (par défaut nasa_challenge) AVANT
-- `python bd/connection.py --manifest ...` : l'importeur ne crée jamais de table lui-même.
CREATE DATABASE IF NOT EXISTS nasa_challenge CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE nasa_challenge;

CREATE TABLE IF NOT EXISTS culture (
    id INT NOT NULL AUTO_INCREMENT,
    ecoportcode INT NOT NULL,
    scientificname VARCHAR(160) NOT NULL,
    comname TEXT NULL,
    famille VARCHAR(80) NULL,
    saison VARCHAR(80) NULL,
    n_fixer TINYINT(1) NULL,
    t_base DOUBLE NULL,
    t_upper DOUBLE NULL,
    gdd_maturite DOUBLE NULL,
    kc_mid DOUBLE NULL,
    kc_ini DOUBLE NULL,
    kc_end DOUBLE NULL,
    zr_mm DOUBLE NULL,
    ph_min DOUBLE NULL,
    ph_max DOUBLE NULL,
    ph_opt DOUBLE NULL,
    duree_cycle DOUBLE NULL,
    semis_mois INT NULL,
    semis_jour INT NULL,
    recolte_mois INT NULL,
    recolte_jour INT NULL,
    seuil_praticable DOUBLE NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_culture_ecoportcode (ecoportcode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
