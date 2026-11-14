import os
import requests
import pandas as pd

API_URL = "https://catalog.agridata.tn/api/3/action/package_search"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def scrape_local_tunisia_datasets(download_files=False, out_dir="data_tunisie_local"):
    # Producteurs locaux : DGACTA (stations + sols), AVFA (stations), DGRE (pluie), ONAGRI (cartes agricoles)
    fq_filters = [
        "organization:(dgacta OR avfa OR dgre OR onagri-dept)",
        "groups:(donnees-climatiques OR amenagement-des-terres-agricoles-conservation-des-eaux-et-du-sol)"
    ]

    records = []
    seen_ids = set()

    for fq in fq_filters:
        params = {"fq": fq, "rows": 200}
        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=25)
        resp.raise_for_status()
        results = resp.json().get("result", {}).get("results", [])

        for pkg in results:
            if pkg["id"] in seen_ids:
                continue
            seen_ids.add(pkg["id"])

            org = pkg.get("organization", {}).get("name", "")
            for res in pkg.get("resources", []):
                fmt = (res.get("format") or "").upper()
                url = res.get("url", "")
                records.append({
                    "producteur": org,
                    "dataset": pkg.get("title"),
                    "ressource": res.get("name"),
                    "format": fmt,
                    "date_maj": pkg.get("metadata_modified"),
                    "url": url
                })

                # Option : télécharger automatiquement les CSV / XLSX locaux
                if download_files and fmt in {"CSV", "XLS", "XLSX"} and url:
                    os.makedirs(out_dir, exist_ok=True)
                    safe_name = f"{org}_{pkg['name']}_{res['id'][:8]}.{fmt.lower()}"
                    filepath = os.path.join(out_dir, safe_name)
                    try:
                        r_file = requests.get(url, headers=HEADERS, timeout=30)
                        if r_file.ok:
                            with open(filepath, "wb") as f:
                                f.write(r_file.content)
                    except Exception as e:
                        print(f"Erreur téléchargement {url}: {e}")

    df = pd.DataFrame(records)
    df.to_csv("catalogue_local_tunisie.csv", index=False, encoding="utf-8-sig")
    print(f"{len(df)} ressources locales répertoriées (dont {len(df[df['format']=='CSV'])} fichiers CSV).")
    return df

if __name__ == "__main__":
    df_local = scrape_local_tunisia_datasets(download_files=True)
    print(df_local[["producteur", "dataset", "ressource", "format"]].head(15))