"""Tests de bout en bout du pipeline sur l'échantillon synthétique (tests/make_sample.py).

Le pipeline tourne en local (DATA_ROOT = dossier temporaire) : mêmes scripts que sur
Onyxia, sans S3. Lancement : make test  (ou  python -m pytest -v tests)
"""
import csv
import glob
import os
import subprocess
import sys

import duckdb
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import make_sample  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")


def run(args, data_root):
    env = {**os.environ, "DATA_ROOT": str(data_root), "SHUFFLE_PARTITIONS": "2",
           # Spark bridé comme sur Onyxia : sans cela, "python script.py" prend tous les
           # cœurs du serveur (local[*]) et peut dépasser la mémoire du service.
           "PYSPARK_SUBMIT_ARGS": "--master local[2] --driver-memory 512m pyspark-shell"}
    env.pop("AWS_ACCESS_KEY_ID", None)  # aucun accès S3 pendant les tests
    return subprocess.run([sys.executable, *args], cwd=SRC, env=env,
                          capture_output=True, text=True, timeout=900)


def parquet(data_root, table):
    return duckdb.sql(f"SELECT * FROM read_parquet('{data_root}/processed/gold/{table}/*.parquet')").df()


@pytest.fixture(scope="module")
def data_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("data")
    make_sample.generer(str(root))
    r = run(["spark_pipeline.py", "--stage", "all"], root)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    return root


def test_controles_qualite(data_root):
    """L'étape silver détecte exactement les défauts injectés."""
    fichier = glob.glob(f"{data_root}/processed/quality/*.csv")[0]
    with open(fichier, encoding="utf-8") as f:
        rapport = {(r["table"], r["controle"]): int(r["nb_lignes"]) for r in csv.DictReader(f)}
    for controle, attendu in make_sample.DEFAUTS.items():
        assert rapport[("conso", controle)] == attendu, controle
    assert rapport[("jointure", "communes_conso_sans_population")] == 1
    assert rapport[("jointure", "communes_population_sans_conso")] == 1


def test_tables_gold(data_root):
    hab = parquet(data_root, "conso_par_habitant")
    assert len(hab) == 5 * 3                       # 5 communes avec population x 3 années
    assert hab["energie_res_kwh_hab"].gt(0).all()
    top = parquet(data_root, "top_communes_2000hab")
    assert top["population"].ge(2000).all() and len(top) == 3 * 3
    for table in ["conso_par_secteur", "synthese_departement"]:
        assert len(parquet(data_root, table)) > 0


def test_verification_duckdb(data_root):
    """Contrôle indépendant : DuckDB retrouve les valeurs de Spark (code retour 0)."""
    r = run(["verify_duckdb.py"], data_root)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert "15/15 communes-années conformes" in r.stdout


def test_relance_une_table_gold(data_root):
    """--table ne recalcule que la table demandée, sans toucher aux autres."""
    cible = f"{data_root}/processed/gold/top_communes_2000hab"
    autre = glob.glob(f"{data_root}/processed/gold/conso_par_habitant/*.parquet")[0]
    date_autre = os.path.getmtime(autre)
    subprocess.run(["rm", "-rf", cible], check=True)          # simule un arrêt en cours d'étape
    r = run(["spark_pipeline.py", "--stage", "gold", "--table", "top_communes_2000hab"], data_root)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert os.path.exists(f"{cible}/_SUCCESS")
    assert os.path.getmtime(autre) == date_autre               # conso_par_habitant non réécrite
    assert len(parquet(data_root, "top_communes_2000hab")) == 9


def test_table_sans_stage_gold_refusee(tmp_path):
    r = run(["spark_pipeline.py", "--stage", "silver", "--table", "conso_par_secteur"], tmp_path)
    assert r.returncode != 0 and "--stage gold" in r.stderr
