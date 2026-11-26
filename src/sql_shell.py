"""Console SQL interactive (DuckDB) sur les tables gold stockées sur S3.
Tables : hab (commune x année), secteur (année x filière x secteur), synthese (département x année).
Tapez une requête terminée par ; puis Entrée. Tapez quit pour sortir."""
from datetime import datetime
import pandas as pd
import config as C
from verify_duckdb import connect, p

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)
con = connect()
for vue, table in [("hab", "conso_par_habitant"), ("secteur", "conso_par_secteur"),
                   ("synthese", "synthese_departement")]:
    con.execute(f"CREATE VIEW {vue} AS SELECT * FROM read_parquet('{p(C.GOLD_DIR)}/{table}/*.parquet')")
print(__doc__)
buffer = []
while True:
    try:
        ligne = input("sql> " if not buffer else "...> ")
    except EOFError:
        break
    if not buffer and ligne.strip().lower() in ("quit", "exit"):
        break
    buffer.append(ligne)
    if ligne.rstrip().endswith(";"):
        requete = "\n".join(buffer).rstrip().rstrip(";")
        buffer = []
        try:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] namespace/bucket : {C.S3_BUCKET}")
            print(con.execute(requete).df().to_string(index=False))
        except Exception as e:
            print(f"Erreur : {e}")
