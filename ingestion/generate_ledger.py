"""
Genere le grand livre fictif d'un groupe multi-entites (4 filiales, 4 devises)
et le budget mensuel associe.

Sorties (data/raw/) :
  - entities.csv            referentiel des entites
  - chart_of_accounts.csv   plan de comptes simplifie (type PCG)
  - gl_entries.csv          ecritures comptables (une ligne = un mouvement debit ou credit)
  - budget.csv              budget mensuel par entite et par compte de resultat

Le generateur est deterministe (graine fixe) : relancer le pipeline donne le meme
grand livre, ce qui rend les chargements idempotents.
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42

ENTITIES = pd.DataFrame(
    [
        # entity_id, nom, pays, devise, poids relatif dans le CA du groupe
        ("FR01", "FinGroup France SAS", "FR", "EUR", 1.00),
        ("UK01", "FinGroup UK Ltd", "GB", "GBP", 0.55),
        ("US01", "FinGroup US Inc", "US", "USD", 0.80),
        ("PL01", "FinGroup Polska Sp. z o.o.", "PL", "PLN", 0.35),
    ],
    columns=["entity_id", "entity_name", "country", "currency", "size_factor"],
)

# Plan de comptes simplifie. pnl_line = ligne du compte de resultat de gestion.
CHART_OF_ACCOUNTS = pd.DataFrame(
    [
        ("706000", "Prestations de services", "P&L", "Chiffre d'affaires", 1),
        ("601000", "Achats de sous-traitance", "P&L", "Couts directs", 2),
        ("641000", "Remunerations du personnel", "P&L", "Frais de personnel", 3),
        ("645000", "Charges sociales", "P&L", "Frais de personnel", 3),
        ("613000", "Locations", "P&L", "Frais generaux", 4),
        ("625000", "Deplacements", "P&L", "Frais generaux", 4),
        ("626000", "Telecom et IT", "P&L", "Frais generaux", 4),
        ("681000", "Dotations aux amortissements", "P&L", "Amortissements", 5),
        ("411000", "Clients", "BILAN", None, None),
        ("401000", "Fournisseurs", "BILAN", None, None),
        ("421000", "Personnel, remunerations dues", "BILAN", None, None),
        ("431000", "Securite sociale", "BILAN", None, None),
        ("281000", "Amortissements des immobilisations", "BILAN", None, None),
    ],
    columns=["account_id", "account_name", "statement", "pnl_line", "pnl_order"],
)

# Montant mensuel de reference en EUR pour une entite de size_factor = 1.
# Signe : montant "naturel" du compte (positif). Le sens debit/credit est gere plus bas.
BASE_MONTHLY_EUR = {
    "706000": 1_200_000,
    "601000": 420_000,
    "641000": 380_000,
    "645000": 160_000,
    "613000": 45_000,
    "625000": 18_000,
    "626000": 22_000,
    "681000": 30_000,
}

# Contrepartie de bilan pour chaque compte de resultat
COUNTERPART = {
    "706000": "411000",
    "601000": "401000",
    "641000": "421000",
    "645000": "431000",
    "613000": "401000",
    "625000": "401000",
    "626000": "401000",
    "681000": "281000",
}

# Journal comptable de l'ecriture (ventes, achats, paie, operations diverses)
JOURNAL = {
    "706000": "VTE",
    "601000": "ACH",
    "613000": "ACH",
    "625000": "ACH",
    "626000": "ACH",
    "641000": "PAI",
    "645000": "PAI",
    "681000": "OD",
}

# Taux approximatifs, uniquement pour dimensionner les montants en devise locale.
# Les vrais taux de conversion viennent d'Eurostat dans le pipeline.
APPROX_FX = {"EUR": 1.0, "GBP": 0.85, "USD": 1.10, "PLN": 4.30}

# Nombre de factures par mois et par compte (le montant mensuel est reparti dessus)
N_DOCS = {"706000": 40, "601000": 25, "613000": 1, "625000": 15, "626000": 4}


def month_range(start: str, end: str) -> list[date]:
    return [d.date() for d in pd.date_range(start, end, freq="MS")]


def last_closed_month(today: date) -> str:
    first_of_month = today.replace(day=1)
    return (pd.Timestamp(first_of_month) - pd.offsets.MonthBegin(1)).strftime("%Y-%m-%d")


def build_ledger(start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    months = month_range(start, end)
    gl_rows, budget_rows = [], []
    entry_seq = 0

    for ent in ENTITIES.itertuples():
        fx = APPROX_FX[ent.currency]
        for i, m in enumerate(months):
            seasonality = 1 + 0.08 * np.sin(2 * np.pi * (m.month - 3) / 12)
            growth = (1 + 0.004) ** i  # environ +5 % par an
            for account, base in BASE_MONTHLY_EUR.items():
                budget_local = base * ent.size_factor * fx * seasonality * growth
                budget_rows.append(
                    (ent.entity_id, m.strftime("%Y-%m"), account, round(budget_local, 2))
                )
                # Realise = budget +/- un ecart aleatoire (plus volatil sur le CA)
                vol = 0.03 if account == "706000" else 0.02
                actual_total = budget_local * rng.normal(1.0, vol)
                n = N_DOCS.get(account, 1)
                weights = rng.dirichlet(np.ones(n))
                days = rng.integers(1, 28, size=n)
                for w, d in zip(weights, days):
                    entry_seq += 1
                    amount = round(float(actual_total * w), 2)
                    entry_id = f"{ent.entity_id}-{m:%Y%m}-{entry_seq:07d}"
                    posting_date = m.replace(day=int(d))
                    is_revenue = account == "706000"
                    # Produit : credit 706 / debit 411. Charge : debit 6xx / credit contrepartie.
                    lines = [
                        (account, 0.0, amount) if is_revenue else (account, amount, 0.0),
                        (COUNTERPART[account], amount, 0.0)
                        if is_revenue
                        else (COUNTERPART[account], 0.0, amount),
                    ]
                    for line_no, (acc, debit, credit) in enumerate(lines, start=1):
                        gl_rows.append(
                            (
                                entry_id,
                                line_no,
                                ent.entity_id,
                                posting_date.isoformat(),
                                acc,
                                debit,
                                credit,
                                ent.currency,
                                JOURNAL[account],
                            )
                        )

    gl = pd.DataFrame(
        gl_rows,
        columns=[
            "entry_id",
            "line_no",
            "entity_id",
            "posting_date",
            "account_id",
            "debit_local",
            "credit_local",
            "currency",
            "journal_code",
        ],
    )
    budget = pd.DataFrame(
        budget_rows, columns=["entity_id", "period", "account_id", "budget_local"]
    )
    return gl, budget


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default=last_closed_month(date.today()))
    parser.add_argument("--out", default="data/raw")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    gl, budget = build_ledger(args.start, args.end)

    ENTITIES.drop(columns="size_factor").to_csv(out / "entities.csv", index=False)
    # Int64 (entier nullable) : evite d'ecrire "1.0" pour les comptes de bilan sans ordre
    CHART_OF_ACCOUNTS.astype({"pnl_order": "Int64"}).to_csv(
        out / "chart_of_accounts.csv", index=False
    )
    gl.to_csv(out / "gl_entries.csv", index=False)
    budget.to_csv(out / "budget.csv", index=False)
    print(f"gl_entries.csv : {len(gl):,} lignes | budget.csv : {len(budget):,} lignes")


if __name__ == "__main__":
    main()
