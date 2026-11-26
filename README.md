# Consommation d'électricité et de gaz par commune et par habitant (Saône-et-Loire)

## Auteurs
- NONO TALLA Fortune Alvarez
- NOM Prénom (binôme)

## Prérequis
- Compte Onyxia, service **VSCode-pyspark** lancé avec le rôle Kubernetes `admin`.
- Dans le service : `pip install -r src/requirements.txt` (`kubectl`, `mc` et Spark sont déjà installés).

## Jeu de données
| | |
|---|---|
| Consommation | « Consommation annuelle d'électricité et gaz par commune », Agence ORE : https://opendata.agenceore.fr/datasets/consommation-annuelle-d-electricite-et-gaz-par-commune |
| Population | Population légale des communes (INSEE), API Géo : https://geo.api.gouv.fr/communes |
| Licence | Licence Ouverte / Open Licence v2.0 (Etalab) pour les deux sources |
| Périmètre | Département 71 (Saône-et-Loire), années 2022 et 2023, 17 colonnes |
| Téléchargement | JJ/MM/2026 |
| Taille brute | X,XX Mo (affichée par `download_data.py`) |

## Contexte et choix de l'étude
Depuis la loi de transition énergétique de 2015, les gestionnaires de réseaux publient la consommation d'énergie de chaque commune. Ces données servent aux collectivités pour suivre leur consommation et cibler leurs actions (rénovation, chauffage). Nous avons choisi ce sujet pour trois raisons : il est lié à notre parcours data dans l'industrie et l'énergie, il oblige à joindre deux sources publiques (Agence ORE et INSEE), et les données contiennent de vrais défauts à traiter (secret statistique, secteurs inconnus, communes sans population). Le périmètre (un département, deux années) respecte la limite de 1 à 5 Mo. Les années 2022 et 2023 suivent la même méthode de calcul : l'Agence ORE l'a changée en 2022.

## Problématique
Quelles communes de Saône-et-Loire consomment le plus d'électricité et de gaz résidentiels par habitant, et comment cette consommation a-t-elle évolué entre 2022 et 2023 ? Le résultat est recalculé indépendamment avec DuckDB et comparé à la datavisualisation officielle de l'Agence ORE.

## Chemins S3
| Couche | Chemin (`s3://<id-onyxia>/bigdata_project/...`) |
|---|---|
| Brut | `raw/conso_elec_gaz_communes.csv`, `raw/population_communes.csv` |
| Bronze | `processed/bronze/{conso,population}/` (Parquet) |
| Silver | `processed/silver/conso/` (partitionné par `annee`), `processed/silver/population/` |
| Gold | `processed/gold/{conso_par_habitant,conso_par_secteur}/` |
| Contrôles | `processed/quality/` (qualité), `processed/verification/` (vérification) |

## Reproduction
```bash
git clone https://github.com/alvarez237/Projet-Big-Data.git && cd Projet-Big-Data
pip install -r src/requirements.txt
export S3_BUCKET=<id-onyxia>                          # nom affiché par : mc ls s3/
python src/download_data.py --out data/raw            # 1. téléchargement (Agence ORE + INSEE)
bash src/upload_raw.sh data/raw                       # 2. dépôt du brut sur S3
cd src && spark-submit spark_pipeline.py --stage all  # 3. pipeline Spark bronze -> silver -> gold
python verify_duckdb.py && cd ..                      # 4. vérification indépendante DuckDB
bash src/run_k8s.sh all                               # 5. même pipeline en Jobs Kubernetes
python src/benchmark.py --raw data/raw/conso_elec_gaz_communes.csv   # 6. mesures x1/x10/x100
```
**Relance :** si une étape échoue, on la relance seule (`--stage bronze`, `silver` ou `gold`, ou `bash src/run_k8s.sh silver`). Chaque étape relit la couche précédente sur S3 et l'écrase, sans rien refaire d'autre. Les traces d'exécution sont dans `logs/`, les captures dans `evidence/`.
