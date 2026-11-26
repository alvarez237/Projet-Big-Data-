"""Configuration commune du projet (lue depuis les variables d'environnement).

Sur Onyxia, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN et
AWS_S3_ENDPOINT sont injectées automatiquement dans les services.
"""
import os

# Périmètre étudié : départements (codes INSEE) et années
DEPARTEMENTS = os.environ.get("DEPARTEMENTS", "71,21,58,89").split(",")
ANNEES = os.environ.get("ANNEES", "2022,2023,2024").split(",")

# Bucket personnel Onyxia : il porte le nom du namespace Kubernetes du service.
# On le lit automatiquement, ce qui évite un "export S3_BUCKET" manuel
# (l'ancienne valeur par défaut, $USER, est vide sur Onyxia et ne correspond à aucun bucket).
NAMESPACE_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"


def _bucket_par_defaut():
    try:
        with open(NAMESPACE_FILE) as f:
            return f.read().strip()
    except OSError:  # hors Onyxia : pas de namespace, il faut définir S3_BUCKET
        return "mon-id-onyxia"


S3_BUCKET = os.environ.get("S3_BUCKET") or _bucket_par_defaut()
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
