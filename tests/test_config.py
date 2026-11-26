"""Tests de la détection du bucket S3 (src/config.py)."""
import importlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))


def charger(monkeypatch, env):
    for var in ["S3_BUCKET", "DATA_ROOT"]:
        monkeypatch.delenv(var, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import config
    return importlib.reload(config)


def test_bucket_lu_depuis_le_namespace(monkeypatch, tmp_path):
    ns = tmp_path / "namespace"
    ns.write_text("user-test-ece\n")
    C = charger(monkeypatch, {})
    monkeypatch.setattr(C, "NAMESPACE_FILE", str(ns))
    assert C._bucket_par_defaut() == "user-test-ece"


def test_variable_s3_bucket_prioritaire(monkeypatch):
    C = charger(monkeypatch, {"S3_BUCKET": "mon-bucket"})
    assert C.S3_BUCKET == "mon-bucket"
    assert C.DATA_ROOT == "s3a://mon-bucket/bigdata_project"


def test_hors_onyxia_valeur_explicite(monkeypatch):
    C = charger(monkeypatch, {})
    monkeypatch.setattr(C, "NAMESPACE_FILE", "/chemin/inexistant")
    assert C._bucket_par_defaut() == "mon-id-onyxia"
