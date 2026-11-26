"""Génère un petit jeu de données SYNTHÉTIQUE au format des fichiers bruts du projet.

Il sert uniquement aux tests automatisés (Makefile, GitHub Actions) : la CI n'a pas
accès au S3 d'Onyxia. Les défauts de qualité sont injectés volontairement et en
nombre connu, pour vérifier que l'étape silver les détecte tous.

Usage : python tests/make_sample.py <dossier>   ->  <dossier>/raw/*.csv
"""
import csv
import os
import sys

CONSO_FIELDS = ["operateur", "filiere", "annee", "code_commune", "nom_commune",
                "code_departement", "code_categorie_consommation", "code_grand_secteur",
                "code_secteur_naf2", "nb_sites", "conso_totale_mwh", "conso_moyenne_mwh"]

# code, nom, population (None = commune sans population INSEE)
COMMUNES = [
    ("21001", "Alpha-sur-Ouche", 450),
    ("21002", "Beta-les-Vignes", 2500),
    ("21003", "Gamma", 3200),
    ("71001", "Delta-en-Bresse", 180),
    ("71002", "Epsilon", 6400),
    ("71003", "Zeta-sans-Insee", None),   # présente dans la conso, absente de l'INSEE
]
POP_SANS_CONSO = ("71004", "Eta-sans-Conso", 900)  # présente à l'INSEE, absente de la conso
ANNEES = [2022, 2023, 2024]

# Défauts injectés (nombres attendus par tests/test_pipeline.py)
DEFAUTS = {
    "doublons_exacts": 1,
    "consommation_absente (secret statistique)": 2,
    "consommation_negative": 1,
    "code_commune_invalide": 1,
    "secteur_ou_categorie_inconnu": 1,
}


def ligne(filiere, annee, code, nom, cat, secteur, nb_sites, total):
    moyenne = "" if total == "" else round(total / nb_sites, 3) if nb_sites else 0
    return {"operateur": "Enedis" if filiere == "Electricité" else "GRDF",
            "filiere": filiere, "annee": annee, "code_commune": code, "nom_commune": nom,
            "code_departement": code[:2], "code_categorie_consommation": cat,
            "code_grand_secteur": secteur, "code_secteur_naf2": "",
            "nb_sites": nb_sites, "conso_totale_mwh": total, "conso_moyenne_mwh": moyenne}


def generer(dossier):
    raw = os.path.join(dossier, "raw")
    os.makedirs(raw, exist_ok=True)
    rows = []
    for i, (code, nom, pop) in enumerate(COMMUNES):
        for k, annee in enumerate(ANNEES):
            base = 1000 + 150 * i - 40 * k   # valeurs déterministes, légère baisse par an
            rows += [
                ligne("Electricité", annee, code, nom, "RES", "RESIDENTIEL", 200 + i, base),
                ligne("Gaz", annee, code, nom, "RES", "RESIDENTIEL", 80 + i, base * 1.5),
                ligne("Electricité", annee, code, nom, "PRO", "TERTIAIRE", 20 + i, base / 2),
                ligne("Gaz", annee, code, nom, "ENT", "INDUSTRIE", 3, base * 2),
            ]
    rows.append(dict(rows[0]))                                                          # doublon exact
    rows.append(ligne("Gaz", 2022, "21001", "Alpha-sur-Ouche", "AGR", "AGRICULTURE", 1, ""))  # secret
    rows.append(ligne("Gaz", 2023, "21002", "Beta-les-Vignes", "AGR", "AGRICULTURE", 1, ""))  # secret
    rows.append(ligne("Electricité", 2024, "21003", "Gamma", "PRO", "TERTIAIRE", 2, -5.0))   # négative
    rows.append(ligne("Electricité", 2024, "XXABC", "Code-Faux", "RES", "RESIDENTIEL", 3, 12.0))  # code
    rows.append(ligne("Electricité", 2024, "71002", "Epsilon", "X", "X", 4, 30.0))           # inconnu

    with open(os.path.join(raw, "conso_elec_gaz_communes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CONSO_FIELDS, delimiter=";")
        w.writeheader()
        w.writerows(rows)

    with open(os.path.join(raw, "population_communes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["code", "nom", "population", "codeDepartement"])
        for code, nom, pop in [*COMMUNES, POP_SANS_CONSO]:
            if pop is not None:
                w.writerow([code, nom, pop, code[:2]])
    return len(rows)


if __name__ == "__main__":
    n = generer(sys.argv[1] if len(sys.argv) > 1 else "data_test")
    print(f"échantillon synthétique : {n} lignes de consommation")
