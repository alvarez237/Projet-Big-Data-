"""Table Iceberg pour la couche gold (PyIceberg, catalogue SQLite, données sur S3).

Démontre les apports d'Iceberg par rapport à un simple dossier Parquet :
  1. table transactionnelle avec métadonnées et snapshots (versions) ;
  2. partitionnement par année géré par la table ;
  3. time travel : relire la table telle qu'elle était à un snapshot précédent ;
  4. évolution de schéma sans réécrire les données.

Usage : python src/iceberg_gold.py
"""
import os
from datetime import datetime

import duckdb
import pyarrow as pa
import pyarrow.compute as pc
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.types import BooleanType

import config as C
from verify_duckdb import connect, p

TABLE = "gold.conso_par_habitant"


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def catalog():
    warehouse = p(f"{C.DATA_ROOT}/iceberg")
    props = {"uri": "sqlite:///data/iceberg_catalog.db", "warehouse": warehouse}
    if warehouse.startswith("s3://"):
        props.update({
            "s3.endpoint": f"https://{os.environ.get('AWS_S3_ENDPOINT', 'minio.lab.sspcloud.fr')}",
            "s3.access-key-id": os.environ["AWS_ACCESS_KEY_ID"],
            "s3.secret-access-key": os.environ["AWS_SECRET_ACCESS_KEY"],
            "s3.session-token": os.environ.get("AWS_SESSION_TOKEN", ""),
            "s3.region": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            "s3.force-virtual-addressing": "false",
        })
    else:
        os.makedirs(warehouse, exist_ok=True)
    os.makedirs("data", exist_ok=True)
    return SqlCatalog("projet", **props)


def main():
    log(f"namespace/bucket : {C.S3_BUCKET} - lecture de la table gold Parquet")
    con = connect()
    res = con.execute(
        f"SELECT * FROM read_parquet('{p(C.GOLD_DIR)}/conso_par_habitant/*.parquet') ORDER BY annee, code_commune")
    gold = pa.Table.from_pandas(res.df(), preserve_index=False)
    annees = sorted(set(gold.column("annee").to_pylist()))
    log(f"{gold.num_rows} lignes, années {annees}")

    cat = catalog()
    cat.create_namespace_if_not_exists("gold")
    if cat.table_exists(TABLE):
        cat.drop_table(TABLE)
    t = cat.create_table(TABLE, schema=gold.schema)
    with t.update_spec() as spec:          # partitionnement géré par Iceberg
        spec.add_identity("annee")
    log(f"table Iceberg créée : {t.location()}")

    # 1 snapshot par année chargée : simule des chargements successifs
    for a in annees:
        t.append(gold.filter(pc.equal(gold.column("annee"), a)))
        log(f"append année {a} -> snapshot {t.current_snapshot().snapshot_id}")

    # évolution de schéma : nouvelle colonne, sans réécrire les fichiers existants
    with t.update_schema() as s:
        s.add_column("commune_prioritaire", BooleanType(), doc="énergie résidentielle > 5000 kWh/hab")
    log("schéma évolué : colonne commune_prioritaire ajoutée")

    print("\n=== Historique des snapshots ===")
    for snap in t.snapshots():
        n = t.scan(snapshot_id=snap.snapshot_id).to_arrow().num_rows
        ts = datetime.fromtimestamp(snap.timestamp_ms / 1000)
        print(f"snapshot {snap.snapshot_id}  {ts:%Y-%m-%d %H:%M:%S}  {snap.summary.operation.value:<7} {n:>6} lignes")

    premier = t.snapshots()[0].snapshot_id
    print(f"\n=== Time travel : lignes par année au premier snapshot ({premier}) ===")
    ancien = t.scan(snapshot_id=premier).to_arrow()
    print(duckdb.sql("SELECT annee, COUNT(*) AS lignes FROM ancien GROUP BY annee ORDER BY annee").df().to_string(index=False))

    print("\n=== Requête SQL sur la version actuelle de la table Iceberg ===")
    actuel = t.scan().to_arrow()
    print(duckdb.sql("""SELECT annee, COUNT(*) AS communes, ROUND(AVG(energie_res_kwh_hab)) AS moyenne_kwh_hab
                        FROM actuel GROUP BY annee ORDER BY annee""").df().to_string(index=False))
    print(f"\nPartitionnement : {t.spec()}")
    print(f"Fichiers de métadonnées : {t.metadata_location}")


if __name__ == "__main__":
    main()
