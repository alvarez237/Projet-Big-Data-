# Captures à produire (ID Onyxia + date/heure visibles sur chaque capture)

| Fichier | Contenu |
|---|---|
| 01_service_onyxia.png | Service VSCode-pyspark lancé (namespace visible) |
| 02_download.png | Sortie de `download_data.py` (taille en Mo) |
| 03_s3_raw.png | `mc ls --summarize s3/<id>/bigdata_project/raw/` |
| 04_trace_spark.png | Sortie de `spark_pipeline.py` (étapes bronze, silver, gold avec horodatage) |
| 05_rapport_qualite.png | Tableau des contrôles qualité (étape silver) |
| 06_gold_top10.png | Top 10 des communes (gold/conso_par_habitant) |
| 07_trace_verification.png | Sortie de `verify_duckdb.py` (contrôles 1 et 2) |
| 08_verif_agence_ore.png | Une commune du top 10 sur la datavisualisation Agence ORE |
| 09_k8s_jobs.png | `kubectl get jobs,pods -l app=conso-communes` |
| 10_s3_processed.png | `mc ls --recursive s3/<id>/bigdata_project/processed/` |
| 11_benchmark.png | Sortie de `benchmark.py` |

Avant chaque commande capturée, taper :
`date; kubectl config view --minify -o jsonpath='{..namespace}'; echo`
pour que l'heure et l'identifiant apparaissent dans le terminal.
