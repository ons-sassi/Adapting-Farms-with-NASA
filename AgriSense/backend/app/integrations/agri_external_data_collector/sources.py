"""Registre explicite des sources. Les URL et indicateurs sont documentés, pas présumés validés."""
SOURCES = {
    "nasa_power_point": {
        "name": "NASA POWER - météorologie au point", "provider": "NASA POWER",
        "kind": "json_api", "url": "https://power.larc.nasa.gov/api/temporal/daily/point",
        "description": "Séries météorologiques journalières NASA POWER. Grille/réanalyses et observations satellitaires; estimations, pas mesures de parcelle.",
        "license": "NASA POWER; consulter les conditions et l'attribution de la documentation du service.",
        "geography": "Coordonnées ponctuelles", "frequency": "journalière",
        "data_semantics": "modeled_estimate",
    },
    "soilgrids_profile": {
        "name": "ISRIC SoilGrids - profil pédologique", "provider": "ISRIC",
        "kind": "json_api", "url": "https://rest.isric.org/soilgrids/v2.0/properties/query",
        "description": "Propriétés pédologiques prédites par SoilGrids à une coordonnée, selon les couches/profondeurs disponibles.",
        "license": "ISRIC SoilGrids; consulter la licence et citer la version de données.",
        "geography": "Coordonnées ponctuelles", "frequency": "référence spatiale",
        "data_semantics": "interpolated_estimate",
    },
    "gpm_imerg_v07": {
        "name": "NASA GPM IMERG V07 - précipitations", "provider": "NASA",
        "kind": "gee", "url": "https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_V07",
        "description": "Produit GPM IMERG via Earth Engine. Le connecteur d'indicateurs existe, mais la collecte externe est désactivée.",
        "license": "NASA GPM; vérifier les conditions et citer le produit.",
        "geography": "Coordonnées ponctuelles", "frequency": "journalière",
        "data_semantics": "satellite_estimate",
        "readiness": "configuration_blocked",
        "block_reason": "Configuration et connecteur de collecte externe non disponibles.",
    },
    "smap_l4": {
        "name": "NASA SMAP L4 v008 - humidité du sol", "provider": "NASA",
        "kind": "gee", "url": "https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008",
        "description": "Produit SMAP L4 via Earth Engine. Le connecteur d'indicateurs existe, mais la collecte externe est désactivée.",
        "license": "NASA SMAP; vérifier les conditions et citer le produit.",
        "geography": "Coordonnées ponctuelles", "frequency": "journalière",
        "data_semantics": "satellite_estimate",
        "readiness": "configuration_blocked",
        "block_reason": "Configuration et connecteur de collecte externe non disponibles.",
    },
    "modis_vegetation": {
        "name": "NASA MODIS MOD13Q1 - végétation", "provider": "NASA",
        "kind": "gee", "url": "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13Q1",
        "description": "Produit MODIS via Earth Engine. Le connecteur d'indicateurs existe, mais la collecte externe est désactivée.",
        "license": "NASA LP DAAC; vérifier les conditions et citer le produit.",
        "geography": "Coordonnées ponctuelles ou parcelle", "frequency": "composite 16 jours",
        "data_semantics": "satellite_estimate",
        "readiness": "configuration_blocked",
        "block_reason": "Configuration et connecteur de collecte externe non disponibles.",
    },
    "world_bank_tunisia_agriculture": {
        "name": "World Bank - indicateurs agricoles Tunisie", "provider": "World Bank",
        "kind": "json_api", "url": "https://api.worldbank.org/v2/country/TUN/indicator/{indicator}",
        "default_indicators": ["AG.YLD.CREL.KG", "AG.LND.ARBL.HA", "AG.PRD.CROP.XD", "AG.LND.IRIG.AG.ZS"],
        "description": "Rendements céréaliers, terres arables, indice de production végétale et irrigation. Données nationales, pas des mesures de parcelle.",
        "license": "World Bank open data; vérifier les conditions de réutilisation de chaque série.",
        "geography": "Tunisie", "frequency": "annuelle"
    },
    "faostat_crop_production": {
        "name": "FAOSTAT - production végétale", "provider": "FAO", "kind": "json_api",
        "url": "https://fenixservices.fao.org/faostat/api/v1/en/data/QCL",
        "description": "Production, superficies récoltées et rendements par produit/pays/année selon disponibilité FAOSTAT.",
        "license": "FAO/FAOSTAT; vérifier les conditions de réutilisation et citer FAO.",
        "geography": "Pays", "frequency": "annuelle",
        "default_params": {"area_code": "216", "limit": "1000"}
    },
    "fao_ecocrop_reference": {
        "name": "FAO EcoCrop (référence agronomique)", "provider": "FAO", "kind": "manual_reference",
        "url": "https://www.fao.org/land-water/databases-and-software/ecocrop/en/",
        "description": "Référence de paramètres écologiques des cultures (température, précipitations, altitude, sol). Pas d'API publique stable garantie par ce module : import contrôlé requis.",
        "license": "Consulter les conditions FAO avant réutilisation.", "geography": "Globale", "frequency": "référence"
    },
    "onagri_tunisia": {
        "name": "ONAGRI - observatoire national de l'agriculture", "provider": "ONAGRI",
        "kind": "manual_reference", "url": "https://www.onagri.nat.tn/",
        "description": "Statistiques agricoles, prix, marchés et bulletins tunisiens. Les pages et fichiers évoluent; import CSV/XLSX contrôlé plutôt que scraping fragile.",
        "license": "Vérifier droits de réutilisation et citer le document/bulletin.", "geography": "Tunisie", "frequency": "variable"
    },
    "dgee_tunisia": {
        "name": "DGEDA / statistiques agricoles", "provider": "Ministère de l'Agriculture (Tunisie)",
        "kind": "manual_reference", "url": "https://www.agriculture.tn/",
        "description": "Références nationales sur cultures, superficies, rendements et pratiques. Import documentaire à valider.",
        "license": "Vérifier les droits et la date de chaque publication.", "geography": "Tunisie", "frequency": "variable"
    },
    "fao_fpma": {
        "name": "FAO FPMA - suivi des prix alimentaires", "provider": "FAO", "kind": "manual_reference",
        "url": "https://www.fao.org/giews/food-prices/tool/public/",
        "description": "Prix alimentaires domestiques et internationaux. Source utile au contexte marché, disponibilité pays/produit à vérifier.",
        "license": "FAO; vérifier conditions et attribution.", "geography": "Pays/marchés", "frequency": "variable"
    },
    "world_bank_commodity_prices": {
        "name": "World Bank Commodity Markets (Pink Sheet)", "provider": "World Bank", "kind": "manual_reference",
        "url": "https://www.worldbank.org/en/research/commodity-markets",
        "description": "Prix de référence internationaux de matières premières; ne remplacent pas un prix producteur local tunisien.",
        "license": "World Bank open data; vérifier conditions du fichier.", "geography": "International", "frequency": "mensuelle"
    }
}


def source_readiness(source_id: str) -> tuple[str | None, str | None]:
    source = SOURCES[source_id]
    if source["kind"] != "gee":
        return None, None
    from app.core.config import settings

    if not settings.gee_project:
        return (
            "configuration_blocked",
            "Google Earth Engine n'est pas configuré: définissez GEE_PROJECT dans .env ou l'environnement.",
        )
    if bool(settings.gee_service_account) != bool(settings.gee_key_file):
        return (
            "configuration_blocked",
            "GEE_SERVICE_ACCOUNT et GEE_KEY_FILE doivent être configurés ensemble, ou tous deux omis.",
        )
    return (
        "collector_unavailable",
        "Configuration GEE détectée, mais aucune collecte GEE externe n'est activée; les connecteurs d'indicateurs restent séparés.",
    )


def source_metadata(source_id: str) -> dict:
    metadata = dict(SOURCES[source_id])
    readiness, reason = source_readiness(source_id)
    if readiness:
        metadata["readiness"] = readiness
        metadata["block_reason"] = reason
    return metadata
