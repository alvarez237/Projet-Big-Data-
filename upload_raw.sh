#!/usr/bin/env bash
# Dépôt des données brutes sur le stockage S3 d'Onyxia (client mc préinstallé).
# Usage : bash src/upload_raw.sh [dossier_local]
set -euo pipefail
SRC=${1:-data/raw}
BUCKET=${S3_BUCKET:-$USER}
PREFIX=${S3_PREFIX:-bigdata_project}

mc cp --recursive "$SRC/" "s3/$BUCKET/$PREFIX/raw/"
echo "Contenu de s3/$BUCKET/$PREFIX/raw/ :"
mc ls --summarize "s3/$BUCKET/$PREFIX/raw/"
