"""
Recupere les taux de change mensuels de l'euro publies par Eurostat
(jeu ert_bil_eur_m : taux moyen du mois et taux de fin de mois).

API publique, sans cle : Eurostat Statistics API, format JSON-stat 2.0.
Sortie : data/raw/fx_rates.csv  (period, currency, rate_type, rate)
  rate = nombre d'unites de devise pour 1 EUR (ex. USD 1.08)
"""
from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/ert_bil_eur_m"
CURRENCIES = ["USD", "GBP", "PLN"]
STATINFO = {"AVG": "average", "END": "end_of_period"}


def decode_jsonstat(payload: dict) -> pd.DataFrame:
    """Transforme une reponse JSON-stat (cube multidimensionnel) en table a plat."""
    dim_ids = payload["id"]
    # Pour chaque dimension : liste des codes ordonnes selon leur index
    codes = []
    for dim in dim_ids:
        index = payload["dimension"][dim]["category"]["index"]
        ordered = sorted(index, key=index.get) if isinstance(index, dict) else index
        codes.append(ordered)
    values = payload["value"]  # dict {"position": valeur} ou liste
    rows = []
    for pos, combo in enumerate(itertools.product(*codes)):
        v = values.get(str(pos)) if isinstance(values, dict) else values[pos]
        if v is not None:
            rows.append((*combo, v))
    return pd.DataFrame(rows, columns=[*dim_ids, "value"])


def normalise_period(p: str) -> str:
    # Eurostat renvoie "2024-01" (ou "2024M01" sur d'anciens formats)
    return p.replace("M", "-") if "M" in p else p


def fetch(since: str) -> pd.DataFrame:
    # unit=NAC : unites de devise nationale pour 1 euro
    params = [("format", "JSON"), ("lang", "EN"), ("sinceTimePeriod", since), ("unit", "NAC")]
    params += [("currency", c) for c in CURRENCIES]
    params += [("statinfo", s) for s in STATINFO]
    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    df = decode_jsonstat(resp.json())
    missing = {"time", "currency", "statinfo"} - set(df.columns)
    if missing:
        raise KeyError(f"Dimensions absentes {missing}. Dimensions recues : {list(df.columns)}")

    out = pd.DataFrame(
        {
            "period": df["time"].map(normalise_period),
            "currency": df["currency"],
            "rate_type": df["statinfo"].map(STATINFO),
            "rate": df["value"].astype(float),
        }
    )
    # L'euro vaut 1 : on l'ajoute pour simplifier les jointures dans dbt
    eur = out[["period", "rate_type"]].drop_duplicates().assign(currency="EUR", rate=1.0)
    return (
        pd.concat([out, eur], ignore_index=True)
        .sort_values(["period", "currency", "rate_type"])
        .reset_index(drop=True)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default="2024-01")
    parser.add_argument("--out", default="data/raw")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fx = fetch(args.since)
    fx.to_csv(out / "fx_rates.csv", index=False)
    print(f"fx_rates.csv : {len(fx):,} lignes, de {fx.period.min()} a {fx.period.max()}")


if __name__ == "__main__":
    main()
