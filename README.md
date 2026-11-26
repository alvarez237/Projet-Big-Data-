# Consommation d'électricité et de gaz par commune et par habitant (Côte-d'Or, Nièvre, Saône-et-Loire, Yonne)

## Auteurs
- NONO TALLA Fortune Alvarez
- KOMBIWO Samson Elie

## Prérequis
- Compte Onyxia, service **VSCode-pyspark** (Spark 4, Python, `kubectl` préinstallés) ; variables `AWS_*` injectées par Onyxia.
- Dans le service : `pip install -r src/requirements.txt` (à refaire après chaque redémarrage du service).

## Jeu de données
| | |
|---|---|
| Consommation | « Consommation annuelle d'électricité et gaz par commune », Agence ORE : https://opendata.agenceore.fr/datasets/consommation-annuelle-d-electricite-et-gaz-par-commune |
| Population | Population légale des communes (INSEE), API Géo : https://geo.api.gouv.fr/communes |
| Licence | Licence Ouverte / Open Licence v2.0 (Etalab) pour les deux sources |
| Périmètre | Départements 21, 58, 71, 89 ; années 2022 à 2024 ; 12 colonnes retenues |
| Téléchargement | 26/11/2026 |
| Taille brute | 4,01 Mo : 51 351 lignes de consommation (3,96 Mo) + 1 993 communes (0,05 Mo) |

## Problématique
Depuis 2015, les gestionnaires de réseaux publient la consommation d'électricité et de gaz de chaque commune, mais en volumes bruts qui ne permettent pas de comparer des communes de tailles différentes. Quelles communes de Côte-d'Or, de la Nièvre, de Saône-et-Loire et de l'Yonne consomment le plus d'électricité et de gaz résidentiels par habitant, et comment cette consommation a-t-elle évolué entre 2022 et 2024, période de crise énergétique et de sobriété ? Le projet construit cet indicateur en croisant les données de l'Agence ORE avec la population INSEE, afin de cibler les territoires prioritaires pour la rénovation énergétique.

## Chemins S3 (`s3://user-f-nonotalla-ece/bigdata_project/...`)
| Couche | Préfixe |
|---|---|
| Brut | `raw/conso_elec_gaz_communes.csv`, `raw/population_communes.csv` |
| Bronze | `processed/bronze/{conso,population}/` (Parquet) |
| Silver | `processed/silver/conso/` (partitionné par `annee`), `processed/silver/population/` |
| Gold | `processed/gold/{conso_par_habitant,conso_par_secteur,synthese_departement,top_communes_2000hab}/` |
| Contrôles | `processed/quality/`, `processed/verification/`, `processed/analyse/` |
| Iceberg | `iceberg/gold/conso_par_habitant/` (données partitionnées par `annee` + métadonnées) |

## Reproduction
```bash
git clone https://github.com/alvarez237/Projet-Big-Data-.git && cd Projet-Big-Data-
pip install -r src/requirements.txt
export S3_BUCKET=user-f-nonotalla-ece                     # bucket S3 personnel Onyxia
python src/download_data.py --out data/raw                # 1. téléchargement Agence ORE + INSEE (4,01 Mo)
python src/s3_tool.py upload data/raw raw                 # 2. dépôt du brut sur S3
python src/s3_tool.py ls raw                              #    contrôle du contenu S3
cd src
spark-submit --master "local[2]" --driver-memory 1g spark_pipeline.py --stage all   # 3. bronze -> silver -> gold
python verify_duckdb.py                                   # 4. vérification indépendante Spark vs DuckDB
cd ..
python src/run_analyse.py                                 # 5. requêtes SQL Q1 à Q5 (src/analyse_problematique.sql)
python src/sql_shell.py                                   #    console SQL interactive (optionnel)
python src/iceberg_gold.py                                # 6. couche gold au format Iceberg (snapshots, time travel)
python src/benchmark.py --raw data/raw/conso_elec_gaz_communes.csv --factors 1,10   # 7. mesures pandas/DuckDB/Spark
python src/bench_x100_duckdb.py                           #    mesure x100 (DuckDB en flux)
```
**Relance :** chaque étape Spark relit la couche précédente sur S3 et l'écrase ; en cas d'échec, relancer seulement l'étape concernée (`--stage bronze`, `silver` ou `gold`). Si le service redémarre (mémoire), refaire `pip install` et `export S3_BUCKET`, puis relancer l'étape en arrière-plan : `nohup spark-submit ... > logs/x.log 2>&1 &`.
**Kubernetes :** `bash src/run_k8s.sh all` crée la ConfigMap du code, le Secret S3 et lance les Jobs `conso-pipeline` (Spark, environ 7 min) puis `conso-verify` (DuckDB) ; suivi : `kubectl get jobs,pods -l app=conso-communes`. Prérequis : quota disponible (`kubectl describe resourcequota`) ; supprimer au besoin un ancien service en échec (`helm list`, `helm uninstall <nom>`). Traces d'exécution : `logs/` ; captures : `evidence/`.
