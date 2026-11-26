"""Dépôt et listing des fichiers sur le stockage S3 d'Onyxia (boto3).

Usage :
    python src/s3_tool.py upload data/raw raw     # envoie data/raw/* vers <bucket>/bigdata_project/raw/
    python src/s3_tool.py ls                       # liste tout bigdata_project/ (preuve S3)
    python src/s3_tool.py ls raw                   # liste un seul préfixe
"""
import os
import sys
from datetime import datetime

import boto3

from config import S3_BUCKET as BUCKET, S3_PREFIX as PREFIX  # même bucket que le pipeline
s3 = boto3.client("s3")  # endpoint et clés lus dans les variables AWS_* d'Onyxia


def upload(local_dir, sub):
    for name in sorted(os.listdir(local_dir)):
        path = os.path.join(local_dir, name)
        if os.path.isfile(path):
            key = f"{PREFIX}/{sub}/{name}"
            s3.upload_file(path, BUCKET, key)
            print(f"envoyé : {path} -> s3://{BUCKET}/{key}")


def ls(sub=""):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] s3://{BUCKET}/{PREFIX}/{sub}")
    total, n = 0, 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=f"{PREFIX}/{sub}"):
        for o in page.get("Contents", []):
            print(f"{o['LastModified']:%Y-%m-%d %H:%M}  {o['Size']:>10}  {o['Key']}")
            total, n = total + o["Size"], n + 1
    print(f"{n} objets, {total / 1e6:.2f} Mo")


if __name__ == "__main__":
    if BUCKET == "mon-id-onyxia":
        sys.exit("Bucket introuvable hors Onyxia : export S3_BUCKET=<nom du bucket>")
    if sys.argv[1] == "upload":
        upload(sys.argv[2], sys.argv[3])
    else:
        ls(sys.argv[2] if len(sys.argv) > 2 else "")
