# Raccourcis du projet (à lancer depuis la racine du dépôt, dans un service Onyxia VSCode-pyspark).
# Le bucket S3 est détecté automatiquement (namespace Onyxia) ; on peut le forcer : make pipeline S3_BUCKET=...
# Liste des commandes : make help

PY      ?= python
SPARK   ?= spark-submit --master "local[2]" --driver-memory 1g
STAGE   ?= all
TABLE   ?=
RAW     := data/raw

.DEFAULT_GOAL := help
.PHONY: help install preuve download upload ls pipeline gold verify analyse iceberg bench k8s test lint clean

help: ## Affiche cette aide
	@grep -E '^[a-z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install: ## Installe les dépendances Python (à refaire après chaque redémarrage du service)
	$(PY) -m pip install -q -r src/requirements.txt

preuve: ## Affiche date et namespace (à lancer avant chaque capture d'écran)
	@date; cat /var/run/secrets/kubernetes.io/serviceaccount/namespace 2>/dev/null || echo "(hors Onyxia)"; echo

download: ## 1. Télécharge les données brutes (Agence ORE + INSEE, 4,01 Mo)
	$(PY) src/download_data.py --out $(RAW)

upload: ## 2. Dépose les données brutes sur S3 puis liste le préfixe raw/
	$(PY) src/s3_tool.py upload $(RAW) raw
	$(PY) src/s3_tool.py ls raw

ls: ## Liste le contenu du projet sur S3 (preuve S3)
	$(PY) src/s3_tool.py ls

pipeline: ## 3. Pipeline Spark (STAGE=all|bronze|silver|gold)
	cd src && $(SPARK) spark_pipeline.py --stage $(STAGE)

gold: ## Relance l'étape gold, ou une seule table : make gold TABLE=top_communes_2000hab
	cd src && $(SPARK) spark_pipeline.py --stage gold $(if $(TABLE),--table $(TABLE))

verify: ## 4. Vérification indépendante Spark vs DuckDB (échoue si un écart est trouvé)
	cd src && $(PY) verify_duckdb.py

analyse: ## 5. Requêtes SQL Q1 à Q5
	$(PY) src/run_analyse.py

iceberg: ## 6. Couche gold au format Iceberg
	$(PY) src/iceberg_gold.py

bench: ## 7. Benchmark pandas / DuckDB / Spark (x1, x10) puis DuckDB x100
	$(PY) src/benchmark.py --raw $(RAW)/conso_elec_gaz_communes.csv --factors 1,10
	$(PY) src/bench_x100_duckdb.py

k8s: ## Pipeline et vérification en Jobs Kubernetes
	bash src/run_k8s.sh all

test: ## Tests automatisés sur données synthétiques (sans S3), comme la CI GitHub
	$(PY) -m pytest -v tests

lint: ## Détecte les erreurs de syntaxe et noms indéfinis (ruff)
	$(PY) -m ruff check --select E9,F63,F7,F82 src tests

clean: ## Supprime les fichiers locaux temporaires (les données S3 ne sont pas touchées)
	rm -rf $(RAW) spark-warehouse metastore_db derby.log .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
