"""
Point d'entree unique du pipeline : enchaine les 4 etapes et s'arrete a la premiere erreur.

  1. generation du grand livre et du budget
  2. recuperation des taux Eurostat
  3. chargement dans BigQuery (raw)
  4. dbt build : modeles staging et marts, puis tests de qualite

Utilise par le conteneur Docker et par GitHub Actions.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

# On reutilise exactement l'interpreteur Python qui lance ce script (celui du .venv).
# Ecrire simplement "python" peut, sous Windows, lancer un autre Python sans les bibliotheques.
PYTHON = sys.executable


def find_dbt() -> str:
    """dbt est installe a cote de l'interpreteur (.venv/Scripts ou .venv/bin)."""
    name = "dbt.exe" if sys.platform == "win32" else "dbt"
    local = Path(PYTHON).parent / name
    return str(local) if local.exists() else (shutil.which("dbt") or "dbt")


STEPS = [
    ("Generation du grand livre", [PYTHON, "ingestion/generate_ledger.py"], "."),
    ("Taux de change Eurostat", [PYTHON, "ingestion/fetch_fx.py"], "."),
    ("Chargement BigQuery", [PYTHON, "ingestion/load_bigquery.py"], "."),
    ("dbt build (modeles + tests)", [find_dbt(), "build", "--profiles-dir", "."], "dbt"),
]


def main() -> int:
    for label, cmd, cwd in STEPS:
        print(f"\n=== {label} ===", flush=True)
        start = time.time()
        result = subprocess.run(cmd, cwd=cwd)
        if result.returncode != 0:
            print(f"ECHEC a l'etape : {label} (code {result.returncode})", flush=True)
            return result.returncode
        print(f"OK en {time.time() - start:.1f} s", flush=True)
    print("\nPipeline termine avec succes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
