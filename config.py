"""Configuration commune du projet (lue depuis les variables d'environnement).

Sur Onyxia, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN et
AWS_S3_ENDPOINT sont injectées automatiquement dans les services.
"""
import os

# Périmètre étudié : départements (codes INSEE) et années
DEPARTEMENTS = os.environ.get("DEPARTEMENTS", "71").split(",")
ANNEES = os.environ.get("ANNEES", "2022,2023").split(",")

# Bucket personnel Onyxia = identifiant utilisateur
S3_BUCKET = os.environ.get("S3_BUCKET", os.environ.get("USER", "mon-id-onyxia"))
S3_PREFIX = os.environ.get("S3_PREFIX", "bigdata_project")

# DATA_ROOT permet aussi d'exécuter le pipeline sur un dossier local
DATA_ROOT = os.environ.get("DATA_ROOT", f"s3a://{S3_BUCKET}/{S3_PREFIX}")

CONSO_FILE = "conso_elec_gaz_communes.csv"     # Agence ORE
POP_FILE = "population_communes.csv"           # INSEE via geo.api.gouv.fr

RAW_DIR = f"{DATA_ROOT}/raw"
BRONZE_DIR = f"{DATA_ROOT}/processed/bronze"
SILVER_DIR = f"{DATA_ROOT}/processed/silver"
GOLD_DIR = f"{DATA_ROOT}/processed/gold"
QUALITY_DIR = f"{DATA_ROOT}/processed/quality"
VERIF_DIR = f"{DATA_ROOT}/processed/verification"
