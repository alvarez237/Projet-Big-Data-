"""Pipeline médaillon Spark : raw (CSV) -> bronze -> silver -> gold.

Usage :
    spark-submit src/spark_pipeline.py --stage all       # tout le pipeline
    spark-submit src/spark_pipeline.py --stage gold      # une seule étape

Chaque étape relit la couche précédente sur S3 et l'écrase (mode overwrite).
"""
import argparse
import os
import time
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

import config as C

HERE = os.path.dirname(os.path.abspath(__file__))


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def get_spark():
    b = (SparkSession.builder.appName("conso-communes-pipeline")
         .config("spark.sql.shuffle.partitions", os.environ.get("SHUFFLE_PARTITIONS", "8")))
    if C.DATA_ROOT.startswith("s3a://") and os.environ.get("AWS_ACCESS_KEY_ID"):
        endpoint = os.environ.get("AWS_S3_ENDPOINT", "minio.lab.sspcloud.fr")
        b = (b.config("spark.hadoop.fs.s3a.endpoint", f"https://{endpoint}")
             .config("spark.hadoop.fs.s3a.path.style.access", "true")
             .config("spark.hadoop.fs.s3a.access.key", os.environ["AWS_ACCESS_KEY_ID"])
             .config("spark.hadoop.fs.s3a.secret.key", os.environ["AWS_SECRET_ACCESS_KEY"]))
        if os.environ.get("AWS_SESSION_TOKEN"):
            b = (b.config("spark.hadoop.fs.s3a.session.token", os.environ["AWS_SESSION_TOKEN"])
                 .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                         "org.apache.hadoop.fs.s3a.TemporaryAWSCredentialsProvider"))
    return b.getOrCreate()


def read_csv(spark, name):
    return (spark.read.option("header", True).option("sep", ";")
            .option("inferSchema", False).csv(f"{C.RAW_DIR}/{name}"))


# ---------------------------------------------------------------- bronze
def bronze(spark):
    for name, table in [(C.CONSO_FILE, "conso"), (C.POP_FILE, "population")]:
        df = (read_csv(spark, name)
              .withColumn("_source_file", F.input_file_name())
              .withColumn("_ingest_ts", F.current_timestamp()))
        df.write.mode("overwrite").parquet(f"{C.BRONZE_DIR}/{table}")
        log(f"bronze/{table} : {df.count()} lignes")
        if table == "conso":
            # Périmètre réellement présent dans les données (et non la configuration,
            # qui ne sert qu'au téléchargement et peut différer dans le terminal).
            deps = sorted(r[0] for r in df.select("code_departement").distinct().collect())
            annees = sorted(r[0] for r in df.select("annee").distinct().collect())
            log(f"périmètre des données brutes : départements {deps}, années {annees}")


# ---------------------------------------------------------------- silver
def silver(spark):
    q = []  # (table, contrôle, nb_lignes, traitement)

    # --- consommation
    df = spark.read.parquet(f"{C.BRONZE_DIR}/conso").drop("_source_file", "_ingest_ts")
    q.append(("conso", "lignes_brutes", df.count(), "-"))
    df = (df.withColumn("annee", F.col("annee").cast("int"))
            .withColumn("nb_sites", F.col("nb_sites").cast("int"))
            .withColumn("conso_totale_mwh", F.col("conso_totale_mwh").cast("double"))
            .withColumn("conso_moyenne_mwh", F.col("conso_moyenne_mwh").cast("double"))
            )

    n0 = df.count()
    df = df.dropDuplicates()
    q.append(("conso", "doublons_exacts", n0 - df.count(), "supprimées"))

    n = df.filter(F.col("conso_totale_mwh").isNull()).count()
    q.append(("conso", "consommation_absente (secret statistique)", n, "supprimées"))
    df = df.filter(F.col("conso_totale_mwh").isNotNull())

    n = df.filter(F.col("conso_totale_mwh") < 0).count()
    q.append(("conso", "consommation_negative", n, "supprimées"))
    df = df.filter(F.col("conso_totale_mwh") >= 0)

    bad_code = ~F.col("code_commune").rlike("^[0-9][0-9AB][0-9]{3}$") | F.col("code_commune").isNull()
    n = df.filter(bad_code).count()
    q.append(("conso", "code_commune_invalide", n, "supprimées"))
    df = df.filter(~bad_code)

    unknown = (F.col("code_grand_secteur").isNull()
               | F.upper("code_grand_secteur").isin("X", "INCONNU", "")
               | F.upper("code_categorie_consommation").isin("X", ""))
    n = df.filter(unknown).count()
    q.append(("conso", "secteur_ou_categorie_inconnu", n, "gardées, secteur = INCONNU"))
    df = df.withColumn("code_grand_secteur",
                       F.when(unknown, F.lit("INCONNU")).otherwise(F.upper("code_grand_secteur")))

    n = df.filter((F.col("nb_sites") == 0) & (F.col("conso_totale_mwh") > 0)).count()
    q.append(("conso", "conso_sans_point_de_livraison", n, "signalées"))

    ecart = F.abs(F.col("conso_totale_mwh") / F.col("nb_sites") - F.col("conso_moyenne_mwh"))
    n = df.filter((F.col("nb_sites") > 0) & (ecart > 0.05 * F.col("conso_moyenne_mwh") + 0.01)).count()
    q.append(("conso", "moyenne_incoherente (totale/nb_sites)", n, "signalées"))

    q.append(("conso", "lignes_silver", df.count(), "-"))
    df.write.mode("overwrite").partitionBy("annee").parquet(f"{C.SILVER_DIR}/conso")

    # --- population INSEE
    pop = spark.read.parquet(f"{C.BRONZE_DIR}/population").drop("_source_file", "_ingest_ts")
    q.append(("population", "lignes_brutes", pop.count(), "-"))
    pop = (pop.select(F.col("code").alias("code_commune"), F.col("nom").alias("nom_insee"),
                      F.col("population").cast("int").alias("population"))
              .dropDuplicates(["code_commune"]))
    n = pop.filter(F.col("population").isNull() | (F.col("population") <= 0)).count()
    q.append(("population", "population_absente_ou_nulle", n, "supprimées"))
    pop = pop.filter(F.col("population") > 0)
    pop.write.mode("overwrite").parquet(f"{C.SILVER_DIR}/population")

    # --- cohérence entre les deux sources (jointure)
    communes = df.select("code_commune").distinct()
    n = communes.join(pop, "code_commune", "left_anti").count()
    q.append(("jointure", "communes_conso_sans_population", n, "exclues du calcul par habitant"))
    n = pop.join(communes, "code_commune", "left_anti").count()
    q.append(("jointure", "communes_population_sans_conso", n, "signalées"))

    rep = spark.createDataFrame(q, ["table", "controle", "nb_lignes", "traitement"])
    rep.coalesce(1).write.mode("overwrite").option("header", True).csv(C.QUALITY_DIR)
    rep.show(truncate=False)


# ---------------------------------------------------------------- gold
def gold(spark):
    spark.read.parquet(f"{C.SILVER_DIR}/conso").createOrReplaceTempView("conso")
    spark.read.parquet(f"{C.SILVER_DIR}/population").createOrReplaceTempView("population")
    for name in ["conso_par_habitant", "conso_par_secteur",
                 "synthese_departement", "top_communes_2000hab"]:
        with open(os.path.join(HERE, f"gold_{name}.sql"), encoding="utf-8") as f:
            df = spark.sql(f.read())
        df.write.mode("overwrite").parquet(f"{C.GOLD_DIR}/{name}")
        df.coalesce(1).write.mode("overwrite").option("header", True).csv(f"{C.GOLD_DIR}/{name}_csv")
        log(f"gold/{name} : {df.count()} lignes")
        if name == "conso_par_habitant":
            spark.read.parquet(f"{C.GOLD_DIR}/{name}").createOrReplaceTempView("gold_hab")
            log("Top 10 des communes (énergie résidentielle par habitant, dernière année) :")
            df.filter(F.col("annee") == df.agg(F.max("annee")).first()[0]) \
              .orderBy("rang").show(10, truncate=False)
        elif name == "top_communes_2000hab":
            df.filter(F.col("annee") == df.agg(F.max("annee")).first()[0]) \
              .orderBy("rang").show(10, truncate=False)
        else:
            df.show(50, truncate=False)


STAGES = {"bronze": bronze, "silver": silver, "gold": gold}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stage", default="all", choices=["all", *STAGES])
    a = p.parse_args()
    spark = get_spark()
    spark.sparkContext.setLogLevel("WARN")
    log(f"DATA_ROOT={C.DATA_ROOT} Spark {spark.version} master={spark.sparkContext.master}")
    for name in (STAGES if a.stage == "all" else [a.stage]):
        t = time.time()
        log(f"début étape {name}")
        STAGES[name](spark)
        log(f"fin étape {name} en {time.time() - t:.1f} s")
    spark.stop()


if __name__ == "__main__":
    main()
