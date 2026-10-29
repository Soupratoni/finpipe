"""
Charge les CSV de data/raw/ dans le dataset BigQuery "raw".

Deux modes, choisis automatiquement :
  - GCS_BUCKET defini : depot des fichiers dans Cloud Storage
    (gs://<bucket>/raw/<date>/fichier.csv) puis chargement BigQuery depuis le bucket.
    Necessite un projet avec facturation active (essai gratuit Google Cloud).
  - GCS_BUCKET absent : chargement direct du fichier local (fonctionne en sandbox).

Chaque chargement remplace la table (WRITE_TRUNCATE) : c'est un job de chargement,
pas une requete DML, donc compatible avec le sandbox.

Variables d'environnement :
  GCP_PROJECT_ID  (obligatoire)
  BQ_DATASET      (defaut : raw)
  BQ_LOCATION     (defaut : EU)
  GCS_BUCKET      (optionnel)
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from google.cloud import bigquery

RAW_DIR = Path("data/raw")

# Schemas explicites : on ne laisse pas BigQuery deviner les types.
# (Sur un CSV 100 % texte, la detection automatique ne reconnait pas l'en-tete.)
F = bigquery.SchemaField
SCHEMAS = {
    "entities": [
        F("entity_id", "STRING", "REQUIRED"),
        F("entity_name", "STRING"),
        F("country", "STRING"),
        F("currency", "STRING"),
    ],
    "chart_of_accounts": [
        F("account_id", "STRING", "REQUIRED"),
        F("account_name", "STRING"),
        F("statement", "STRING"),
        F("pnl_line", "STRING"),
        F("pnl_order", "INT64"),
    ],
    "gl_entries": [
        F("entry_id", "STRING", "REQUIRED"),
        F("line_no", "INT64"),
        F("entity_id", "STRING"),
        F("posting_date", "DATE"),
        F("account_id", "STRING"),
        F("debit_local", "NUMERIC"),
        F("credit_local", "NUMERIC"),
        F("currency", "STRING"),
        F("journal_code", "STRING"),
    ],
    "budget": [
        F("entity_id", "STRING"),
        F("period", "STRING"),
        F("account_id", "STRING"),
        F("budget_local", "NUMERIC"),
    ],
    "fx_rates": [
        F("period", "STRING"),
        F("currency", "STRING"),
        F("rate_type", "STRING"),
        F("rate", "FLOAT64"),
    ],
}
TABLES = list(SCHEMAS)


def main() -> None:
    project = os.environ["GCP_PROJECT_ID"]
    dataset = os.getenv("BQ_DATASET", "raw")
    location = os.getenv("BQ_LOCATION", "EU")
    bucket_name = os.getenv("GCS_BUCKET")

    client = bigquery.Client(project=project, location=location)
    client.create_dataset(bigquery.Dataset(f"{project}.{dataset}"), exists_ok=True)

    if bucket_name:
        from google.cloud import storage

        bucket = storage.Client(project=project).bucket(bucket_name)

    for name in TABLES:
        path = RAW_DIR / f"{name}.csv"
        if not path.exists():
            print(f"[skip] {path} absent")
            continue
        table_id = f"{project}.{dataset}.{name}"
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            schema=SCHEMAS[name],
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )

        if bucket_name:
            blob_name = f"raw/{date.today():%Y-%m-%d}/{path.name}"
            bucket.blob(blob_name).upload_from_filename(str(path))
            job = client.load_table_from_uri(
                f"gs://{bucket_name}/{blob_name}", table_id, job_config=job_config
            )
        else:
            with path.open("rb") as f:
                job = client.load_table_from_file(f, table_id, job_config=job_config)

        job.result()
        rows = client.get_table(table_id).num_rows
        print(f"[ok] {table_id} : {rows:,} lignes")


if __name__ == "__main__":
    main()
