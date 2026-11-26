"""Exécute les requêtes SQL analytiques de analyse_problematique.sql avec DuckDB
sur les tables gold stockées sur S3, affiche les résultats et les enregistre en CSV.

Usage : python src/run_analyse.py
"""
import os
import re
from datetime import datetime

import config as C
from verify_duckdb import connect, p

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    con = connect()
    con.execute(f"CREATE VIEW hab AS SELECT * FROM read_parquet('{p(C.GOLD_DIR)}/conso_par_habitant/*.parquet')")
    con.execute(f"CREATE VIEW secteur AS SELECT * FROM read_parquet('{p(C.GOLD_DIR)}/conso_par_secteur/*.parquet')")
    sql = open(os.path.join(HERE, "analyse_problematique.sql"), encoding="utf-8").read()
    blocs = [b.strip() for b in re.split(r"\n(?=-- Q\d)", sql) if b.strip().startswith("-- Q")]
    out = p(f"{C.DATA_ROOT}/processed/analyse")
    if not out.startswith("s3://"):
        os.makedirs(out, exist_ok=True)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] analyse sur {p(C.GOLD_DIR)}")
    for bloc in blocs:
        titre = " ".join(l.lstrip("- ").strip() for l in bloc.splitlines() if l.startswith("--"))
        requete = bloc.rstrip(";")
        df = con.execute(requete).df()
        print(f"\n=== {titre} ===")
        print(df.to_string(index=False))
        num = titre.split(".")[0].lower()
        con.register("res", df)
        con.execute(f"COPY res TO '{out}/{num}.csv' (HEADER, DELIMITER ';')")
    print(f"\nRésultats enregistrés dans {out}")


if __name__ == "__main__":
    main()
