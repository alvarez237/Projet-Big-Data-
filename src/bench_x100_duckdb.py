"""Mesure x100 avec DuckDB seul : fabrication du fichier et calcul en flux, mémoire limitée à 1 Go."""
import time, duckdb
con = duckdb.connect()
con.execute("SET memory_limit='1GB'")
con.execute("""COPY (SELECT r.range AS copie, c.* FROM read_csv('data/raw/conso_elec_gaz_communes.csv', delim=';', header=true) c, range(100) r)
               TO 'data/bench/x100_duckdb.parquet' (FORMAT parquet)""")
n = con.execute("SELECT count(*) FROM 'data/bench/x100_duckdb.parquet'").fetchone()[0]
for i in range(2):
    t = time.perf_counter()
    con.execute("""SELECT copie, annee, code_commune, filiere, SUM(conso_totale_mwh)
                   FROM 'data/bench/x100_duckdb.parquet' WHERE conso_totale_mwh >= 0 GROUP BY ALL""").fetchall()
    print(f"x100 duckdb : {n} lignes, essai {i+1} : {time.perf_counter() - t:.3f} s")
