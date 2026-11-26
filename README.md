# Consommation d'électricité et de gaz par commune et par habitant (Côte-d'Or, Nièvre, Saône-et-Loire, Yonne)

## Auteurs
- NONO TALLA Fortune Alvarez
- KOMBIWO Samson Elie

## Prérequis
- Compte Onyxia, service **VSCode-pyspark** (Spark et Python préinstallés).
- Dans le service : `pip install -r src/requirements.txt`.

## Jeu de données
| | |
|---|---|
| Consommation | « Consommation annuelle d'électricité et gaz par commune », Agence ORE : https://opendata.agenceore.fr/datasets/consommation-annuelle-d-electricite-et-gaz-par-commune |
| Population | Population légale des communes (INSEE), API Géo : https://geo.api.gouv.fr/communes |
| Licence | Licence Ouverte / Open Licence v2.0 (Etalab) pour les deux sources |
| Périmètre | Côte-d'Or (21), Nièvre (58), Saône-et-Loire (71), Yonne (89) ; années 2022 à 2024 ; 12 colonnes retenues |
| Téléchargement | 26/11/2026 |
| Taille brute | 4,01 Mo (51 351 lignes de consommation, 1 993 communes) |

## Contexte
Depuis la loi de transition énergétique de 2015, les gestionnaires de réseaux publient la consommation d'électricité et de gaz de chaque commune, afin d'aider les collectivités à piloter leur politique énergétique. Ces données sont publiées en volumes bruts par secteur d'activité : elles ne permettent pas de comparer directement des communes de tailles différentes. La période 2022-2024, marquée par la crise énergétique et le plan de sobriété, rend utile une mesure fine de l'évolution des consommations des ménages à l'échelle locale.

## Problématique
Quelles communes de Côte-d'Or, de la Nièvre, de Saône-et-Loire et de l'Yonne consomment le plus d'électricité et de gaz résidentiels par habitant, et comment cette consommation a-t-elle évolué entre 2022 et 2024 ? En croisant les données de l'Agence ORE avec la population INSEE, le projet produit un indicateur comparable entre communes, absent des données publiées, qui permet de cibler les territoires prioritaires pour la rénovation énergétique des logements.

## Chemins S3
| Couche | Chemin (`s3://user-f-nonotalla-ece/bigdata_project/...`) |
|---|---|
| Brut | `raw/conso_elec_gaz_communes.csv`, `raw/population_communes.csv` |
| Bronze | `processed/bronze/{conso,population}/` (Parquet) |
| Silver | `processed/silver/conso/` (partitionné par `annee`), `processed/silver/population/` |
| Gold | `processed/gold/{conso_par_habitant,conso_par_secteur}/` |
| Contrôles | `processed/quality/` (qualité), `processed/verification/` (vérification) |

## Reproduction
```bash
git clone https://github.com/alvarez237/Projet-Big-Data-.git && cd Projet-Big-Data-
pip install -r src/requirements.txt
export S3_BUCKET=user-f-nonotalla-ece                 # bucket S3 personnel Onyxia
python src/download_data.py --out data/raw            # 1. téléchargement (Agence ORE + INSEE)
python src/s3_tool.py upload data/raw raw             # 2. dépôt du brut sur S3
python src/s3_tool.py ls raw                          #    contrôle du contenu S3
cd src && spark-submit spark_pipeline.py --stage all  # 3. pipeline Spark bronze -> silver -> gold
python verify_duckdb.py && cd ..                      # 4. vérification indépendante DuckDB
bash src/run_k8s.sh all                               # 5. même pipeline en Jobs Kubernetes
python src/benchmark.py --raw data/raw/conso_elec_gaz_communes.csv   # 6. mesures x1/x10/x100
```
**Relance :** si une étape échoue, on la relance seule (`--stage bronze`, `silver` ou `gold`). Chaque étape relit la couche précédente sur S3 et l'écrase, sans rien refaire d'autre. Les captures d'exécution sont dans `evidence/`.
