"""Registre explicite des sources. Les URL et indicateurs sont documentés, pas présumés validés."""
SOURCES = {
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
