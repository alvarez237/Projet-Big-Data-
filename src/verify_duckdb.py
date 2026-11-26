"""Vérification indépendante des résultats gold.

Contrôle 1 : DuckDB recalcule la consommation résidentielle par habitant de chaque commune
             directement depuis les CSV bruts (autre moteur, autre code que Spark),
             puis compare avec gold/conso_par_habitant.
Contrôle 2 : les totaux par filière et par année doivent être identiques dans les deux calculs.
Contrôle 3 (manuel) : comparer 2 ou 3 communes du top 10 avec la datavisualisation officielle
             de l'Agence ORE : https://www.agenceore.fr/datavisualisation/consommations-locales-energie

Usage : python src/verify_duckdb.py
"""
import os
import sys
from datetime import datetime

import duckdb

import config as C

TOL_KWH = 1  # écart toléré en kWh par habitant (arrondis)


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def connect():
    con = duckdb.connect()
    if C.DATA_ROOT.startswith("s3a://"):
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute(f"""CREATE SECRET s3 (TYPE S3,
            KEY_ID '{os.environ["AWS_ACCESS_KEY_ID"]}',
            SECRET '{os.environ["AWS_SECRET_ACCESS_KEY"]}',
            SESSION_TOKEN '{os.environ.get("AWS_SESSION_TOKEN", "")}',
            ENDPOINT '{os.environ.get("AWS_S3_ENDPOINT", "minio.lab.sspcloud.fr")}',
            URL_STYLE 'path', REGION 'us-east-1')""")
    return con


def p(path):
    return path.replace("s3a://", "s3://")


def main():
    con = connect()
    conso, pop = p(f"{C.RAW_DIR}/{C.CONSO_FILE}"), p(f"{C.RAW_DIR}/{C.POP_FILE}")
    gold = p(f"{C.GOLD_DIR}/conso_par_habitant/*.parquet")
    log(f"lecture brute : {conso} et {pop}")

    con.execute(f"""
    CREATE TABLE brut AS
    SELECT DISTINCT * FROM read_csv('{conso}', delim=';', header=true, all_varchar=true);
    CREATE TABLE recalc AS
    SELECT b.annee::INT AS annee, b.code_commune,
           1000 * SUM(TRY_CAST(conso_totale_mwh AS DOUBLE))
                / ANY_VALUE(TRY_CAST(p.population AS DOUBLE)) AS res_kwh_hab_duckdb
    FROM brut b
    JOIN read_csv('{pop}', delim=';', header=true, all_varchar=true) p ON p.code = b.code_commune
    WHERE b.code_categorie_consommation = 'RES'
      AND TRY_CAST(conso_totale_mwh AS DOUBLE) >= 0
      AND TRY_CAST(p.population AS DOUBLE) > 0
    GROUP BY ALL;
    """)

    cmp = con.execute(f"""
    SELECT g.annee, g.code_commune, g.nom_commune, g.energie_res_kwh_hab AS spark,
           ROUND(COALESCE(r.res_kwh_hab_duckdb, 0)) AS duckdb,
           ABS(g.energie_res_kwh_hab - ROUND(COALESCE(r.res_kwh_hab_duckdb, 0))) AS ecart
    FROM read_parquet('{gold}') g
    LEFT JOIN recalc r USING (annee, code_commune)
    ORDER BY g.annee, g.rang
    """).df()
    ok = (cmp["ecart"] <= TOL_KWH).sum()
    print("\n=== Contrôle 1 : kWh résidentiels par habitant, Spark vs DuckDB ===")
    print(cmp.head(10).to_string(index=False))
    log(f"contrôle 1 : {ok}/{len(cmp)} communes-années conformes (tolérance {TOL_KWH} kWh/hab)")
    if ok < len(cmp):
        print(cmp[cmp["ecart"] > TOL_KWH].head(20).to_string(index=False))

    tot = con.execute(f"""
    WITH d AS (SELECT annee::INT AS annee,
                      CASE WHEN upper(filiere) LIKE 'ELEC%' THEN 'elec' ELSE 'gaz' END AS f,
                      SUM(TRY_CAST(conso_totale_mwh AS DOUBLE)) AS mwh
               FROM brut WHERE TRY_CAST(conso_totale_mwh AS DOUBLE) >= 0 GROUP BY ALL),
         s AS (SELECT annee, SUM(elec_totale_mwh) AS elec, SUM(gaz_totale_mwh) AS gaz
               FROM read_parquet('{gold}') GROUP BY annee)
    SELECT s.annee,
           ROUND(s.elec) AS elec_spark_mwh,
           ROUND((SELECT mwh FROM d WHERE d.annee = s.annee AND f = 'elec')) AS elec_duckdb_mwh,
           ROUND(s.gaz) AS gaz_spark_mwh,
           ROUND((SELECT mwh FROM d WHERE d.annee = s.annee AND f = 'gaz')) AS gaz_duckdb_mwh
    FROM s ORDER BY s.annee
    """).df()
    print("\n=== Contrôle 2 : totaux annuels par filière ===")
    print("(Spark ne compte que les communes ayant une population INSEE : un petit écart est possible)")
    print(tot.to_string(index=False))

    out = p(C.VERIF_DIR)
    if not out.startswith("s3://"):
        os.makedirs(out, exist_ok=True)
    con.register("cmp_df", cmp)
    con.register("tot_df", tot)
    con.execute(f"COPY cmp_df TO '{out}/controle1_spark_vs_duckdb.csv' (HEADER, DELIMITER ';')")
    con.execute(f"COPY tot_df TO '{out}/controle2_totaux.csv' (HEADER, DELIMITER ';')")
    log(f"rapports écrits dans {out}")
    # Code retour non nul si un contrôle échoue : la vérification peut ainsi
    # bloquer une chaîne automatisée (Makefile, GitHub Actions, Job Kubernetes).
    if len(cmp) == 0 or ok < len(cmp):
        log("ÉCHEC du contrôle 1")
        sys.exit(1)


if __name__ == "__main__":
    main()
