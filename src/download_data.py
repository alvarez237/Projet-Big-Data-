"""Téléchargement des données brutes.

1. Agence ORE : consommation annuelle d'électricité et de gaz par commune
   (API Data Fair, filtrée sur les départements et années de config.py)
2. INSEE via geo.api.gouv.fr : population légale des communes des mêmes départements

Usage : python src/download_data.py --out data/raw
"""
import argparse
import csv
import os

import requests

from config import ANNEES, CONSO_FILE, DEPARTEMENTS, POP_FILE

ORE_API = ("https://opendata.agenceore.fr/data-fair/api/v1/datasets/"
           "noxwlxv702-ohfyt76f-a3y9/lines")
FIELDS = ["operateur", "filiere", "annee", "code_commune", "nom_commune",
          "code_departement",
          "code_categorie_consommation", "code_grand_secteur", "code_secteur_naf2",
          "nb_sites", "conso_totale_mwh", "conso_moyenne_mwh"]


def download_conso(path):
    dep = " OR ".join(f'"{d}"' for d in DEPARTEMENTS)
    ann = " OR ".join(f'"{a}"' for a in ANNEES)
    params = {"size": 10000, "select": ",".join(FIELDS),
              "qs": f"code_departement:({dep}) AND annee:({ann})"}
    url, n = ORE_API, 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        while url:
            r = requests.get(url, params=params, timeout=120)
            r.raise_for_status()
            page = r.json()
            w.writerows(page["results"])
            n += len(page["results"])
            print(f"  {n} / {page.get('total', n)} lignes")
            url, params = page.get("next"), None   # le lien "next" contient déjà les filtres
    return n


def download_population(path):
    rows = []
    for d in DEPARTEMENTS:
        r = requests.get("https://geo.api.gouv.fr/communes",
                         params={"codeDepartement": d,
                                 "fields": "code,nom,population,codeDepartement"},
                         timeout=60)
        r.raise_for_status()
        rows += r.json()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["code", "nom", "population", "codeDepartement"],
                           delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/raw")
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    print(f"Départements {DEPARTEMENTS}, années {ANNEES}")

    c, pth = download_conso(os.path.join(a.out, CONSO_FILE)), os.path.join(a.out, POP_FILE)
    n = download_population(pth)
    total = 0
    for f in (CONSO_FILE, POP_FILE):
        s = os.path.getsize(os.path.join(a.out, f))
        total += s
        print(f"{f} : {s / 1e6:.2f} Mo")
    print(f"{c} lignes de consommation, {n} communes INSEE")
    print(f"Taille totale des données brutes : {total / 1e6:.2f} Mo")
    if not 1e6 <= total <= 5e6:
        print("ATTENTION : hors de la fourchette 1-5 Mo -> modifier ANNEES ou DEPARTEMENTS")


if __name__ == "__main__":
    main()
