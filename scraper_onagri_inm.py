from io import StringIO
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# 1. Scraper la pluviométrie journalière sur ONAGRI
def scrape_onagri_pluviometrie():
    urls = [
        "https://www.onagri.nat.tn/Pluviometrie-journaliere/fr/181",
        "https://www.onagri.nat.tn/PLUVIOMETRIE/fr/58"
    ]
    tables_trouvees = 0

    for url in urls:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        resp.encoding = "utf-8"

        try:
            # StringIO est obligatoire dans les versions récentes de pandas
            tables = pd.read_html(StringIO(resp.text))
            for table in tables:
                nom_fichier = f"onagri_pluviometrie_table_{tables_trouvees}.csv"
                table.to_csv(nom_fichier, index=False, encoding="utf-8-sig")
                tables_trouvees += 1
        except ValueError:
            # Si la page contient des liens PDF/Excel plutôt qu'un tableau HTML
            soup = BeautifulSoup(resp.text, "html.parser")
            docs = []
            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"])
                if any(ext in href.lower() for ext in (".pdf", ".xls", ".xlsx", ".csv")):
                    docs.append({"titre": a.get_text(strip=True), "lien": href})
            if docs:
                pd.DataFrame(docs).drop_duplicates().to_csv(
                    "onagri_pluviometrie_fichiers.csv", index=False, encoding="utf-8-sig"
                )

    print(f"{tables_trouvees} tableau(x) extrait(s) depuis ONAGRI.")

# 2. Scraper les liens vers les bulletins climatiques PDF de l'INM (meteo.tn)
def scrape_inm_bulletins():
    base_url = "https://www.meteo.tn/fr/actualites"
    resp = requests.get(base_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    bulletins = []
    for a in soup.find_all("a", href=True):
        texte = a.get_text(strip=True)
        href = urljoin(base_url, a["href"])
        if "bulletin" in texte.lower() or "climatique" in texte.lower():
            bulletins.append({"titre": texte, "lien": href})

    df_inm = pd.DataFrame(bulletins).drop_duplicates()
    df_inm.to_csv("bulletins_climatiques_inm.csv", index=False, encoding="utf-8-sig")
    print(f"{len(df_inm)} bulletins INM trouvés.")
    return df_inm

if __name__ == "__main__":
    scrape_onagri_pluviometrie()
    scrape_inm_bulletins()