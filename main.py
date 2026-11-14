"""
main.py : ligne de commande autour de get_indicateurs().

Exemple (Kairouan, blé, dernière saison complète) :
  python main.py --lat 35.68 --lon 10.10 --surface-ha 5 --culture blé --project MON_PROJET_GEE

Avec le polygone de la parcelle (GeoJSON tracé sur la carte) :
  python main.py --geojson parcelle.geojson --culture blé --project MON_PROJET_GEE

Sur un serveur : ajouter --sa-email ... --sa-key cle.json  (compte de service GEE).
Les paramètres de culture sont lus dans MySQL (base nasa_challenge, table culture) :
  python main.py --list-cultures
"""
import argparse
import json

from common import connectors as cn
from indicateurs_service import get_culture, get_indicateurs, lister_cultures, saison
from zonal_service import get_donnees_zonales


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=None)
    ap.add_argument("--lon", type=float, default=None)
    ap.add_argument("--geojson", default=None, help="fichier GeoJSON du polygone de la parcelle")
    ap.add_argument("--surface-ha", type=float, default=None)
    ap.add_argument("--culture", default="blé",
                    help="nom, code EcoPort ou nom scientifique (voir --list-cultures)")
    ap.add_argument("--list-cultures", action="store_true", help="liste les cultures de la base et quitte")
    ap.add_argument("--start", default=None, help="YYYY-MM-DD (défaut : dernière saison complète)")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD")
    ap.add_argument("--project", default=None, help="projet Google Cloud pour Earth Engine")
    ap.add_argument("--sa-email", default=None)
    ap.add_argument("--sa-key", default=None)
    ap.add_argument("--out", default="resultats.json")
    a = ap.parse_args()

    if a.list_cultures:
        for c in lister_cultures():
            print(f"{c['code']:>6}  {c['nom_scientifique']:<26} {c['saison']}  | {', '.join(c['noms'][:4])}")
        return
    if not a.project:
        ap.error("--project est requis (sauf avec --list-cultures)")
    get_culture(a.culture)          # échoue tôt si la culture est absente de la base

    cn.init_gee(a.project, a.sa_email, a.sa_key)
    parcelle = {"lat": a.lat, "lon": a.lon, "surface_ha": a.surface_ha}
    donnees = None
    if a.geojson:
        with open(a.geojson, encoding="utf-8") as f:
            geometry = json.load(f)
        start, end = (a.start, a.end) if (a.start and a.end) else saison(a.culture)
        donnees = get_donnees_zonales(geometry, start, end)
        a.start, a.end = start, end
    elif a.lat is None or a.lon is None:
        ap.error("fournir --lat/--lon ou --geojson")
    res = get_indicateurs(parcelle, a.culture, a.start, a.end, donnees=donnees)

    txt = json.dumps(res, indent=2, ensure_ascii=False)
    print(txt)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(txt)


if __name__ == "__main__":
    main()
