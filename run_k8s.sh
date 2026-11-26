#!/usr/bin/env bash
# Lance le pipeline et la vérification en Jobs Kubernetes dans le namespace Onyxia,
# puis sauvegarde les traces d'exécution.
# Usage : bash src/run_k8s.sh [all|bronze|silver|gold]
set -euo pipefail
cd "$(dirname "$0")/.."
STAGE=${1:-all}
NS=$(kubectl config view --minify -o jsonpath='{..namespace}')
LOGS=logs; mkdir -p "$LOGS"
echo "Namespace : $NS - $(date '+%Y-%m-%d %H:%M:%S')"

# Code et paramètres
kubectl create configmap conso-code --from-file=src/ --dry-run=client -o yaml | kubectl apply -f -
kubectl create configmap conso-params \
  --from-literal=S3_BUCKET="${S3_BUCKET:-$USER}" \
  --from-literal=S3_PREFIX="${S3_PREFIX:-bigdata_project}" \
  --from-literal=DEPARTEMENTS="${DEPARTEMENTS:-71}" \
  --from-literal=ANNEES="${ANNEES:-2022,2023}" \
  --from-literal=AWS_S3_ENDPOINT="$AWS_S3_ENDPOINT" \
  --dry-run=client -o yaml | kubectl apply -f -
# Identifiants S3 du service Onyxia, transmis aux pods des Jobs
kubectl create secret generic s3-credentials \
  --from-literal=AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  --from-literal=AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  --from-literal=AWS_SESSION_TOKEN="${AWS_SESSION_TOKEN:-}" \
  --dry-run=client -o yaml | kubectl apply -f -

run_job () {
  local name=$1 file=$2
  kubectl delete job "$name" --ignore-not-found
  sed "s/value: \"all\" /value: \"$STAGE\" /" "$file" | kubectl apply -f -
  kubectl wait --for=condition=complete "job/$name" --timeout=900s \
    || { kubectl logs "job/$name" | tail -50; exit 1; }
  kubectl get pods -l "job-name=$name" -o wide
  kubectl logs "job/$name" | tee "$LOGS/${name}_$(date +%Y%m%d_%H%M%S).log"
}

run_job conso-pipeline k8s/job-pipeline.yaml
if [ "$STAGE" = "all" ] || [ "$STAGE" = "gold" ]; then
  run_job conso-verify k8s/job-verify.yaml
fi
kubectl get jobs -l app=conso-communes
