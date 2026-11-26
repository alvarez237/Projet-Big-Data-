"""Mesures comparatives pandas / DuckDB / Spark sur le calcul gold
(consommation par commune, année et filière), avec les données x1, x10 et x100.

Sert à justifier le choix des outils et à répondre à « et si les données
étaient 100 fois plus grandes ? ».

Usage : python src/benchmark.py --raw data/raw/conso_elec_gaz_communes.csv --out data/bench
"""
import argparse
import os
import platform
import time

import duckdb
import pandas as pd

COLS = ["annee", "code_commune", "filiere", "code_categorie_consommation", "conso_totale_mwh"]


def build(raw, out, factor):
    path = f"{out}/x{factor}.parquet"
    if not os.path.exists(path):
        df = pd.read_csv(raw, sep=";", usecols=COLS, dtype={"code_commune": str})
        pd.concat([df.assign(copie=i) for i in range(factor)]).to_parquet(path, index=False)
    return path


def t_pandas(path):
    t = time.perf_counter()
    df = pd.read_parquet(path)
    df = df[df["conso_totale_mwh"] >= 0]
    df.groupby(["copie", "annee", "code_commune", "filiere"])["conso_totale_mwh"].sum()
    return time.perf_counter() - t


def t_duckdb(path):
    t = time.perf_counter()
    duckdb.connect().execute(f"""SELECT copie, annee, code_commune, filiere, SUM(conso_totale_mwh)
        FROM read_parquet('{path}') WHERE conso_totale_mwh >= 0 GROUP BY ALL""").fetchall()
    return time.perf_counter() - t


def t_spark(spark, path):
    from pyspark.sql import functions as F
    t = time.perf_counter()
    (spark.read.parquet(path).filter("conso_totale_mwh >= 0")
     .groupBy("copie", "annee", "code_commune", "filiere")
     .agg(F.sum("conso_totale_mwh")).collect())
    return time.perf_counter() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", default="data/bench")
    ap.add_argument("--factors", default="1,10,100")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--engines", default="pandas,duckdb,spark")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    from pyspark.sql import SparkSession
    spark = (SparkSession.builder.master(os.environ.get("SPARK_MASTER", "local[*]"))
             .config("spark.sql.shuffle.partitions", "8")
             .config("spark.ui.showConsoleProgress", "false").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    rows = []
    for f in [int(x) for x in a.factors.split(",")]:
        path = build(a.raw, a.out, f)
        n = len(pd.read_parquet(path, columns=["copie"]))
        t_spark(spark, path)  # préchauffage de la JVM
        for name, fn in [("pandas", t_pandas), ("duckdb", t_duckdb),
                         ("spark", lambda q: t_spark(spark, q))]:
            if name not in a.engines.split(","):
                continue
            ts = [fn(path) for _ in range(a.repeat)]
            rows.append((f, n, round(os.path.getsize(path) / 1e6, 2), name,
                         round(min(ts), 3), round(sum(ts) / len(ts), 3)))
            print(rows[-1], flush=True)

    res = pd.DataFrame(rows, columns=["facteur", "lignes", "parquet_mo", "moteur",
                                      "temps_min_s", "temps_moyen_s"])
    res["machine"] = f"{platform.node()} ({os.cpu_count()} CPU)"
    res.to_csv(f"{a.out}/benchmark.csv", sep=";", index=False)
    print(res.to_string(index=False))
    spark.stop()


if __name__ == "__main__":
    main()
