"""
CapTax AI - LTCG / STCG Tax Classification Module
Owner: Shraddha Singh (Team Lead & AI/Interpretation Lead) — interpretation layer for LTCG/STCG
(currently rule-based; Week 5 scope is to swap in LLM-assisted interpretation via LangChain)

Classifies each realized gain/loss record as Long-Term or Short-Term
Capital Gain based on Indian holding-period rules for listed equity
(> 365 days = LTCG), and applies simplified current-regime tax rates.

Simplifications for this academic version:
  - Grandfathering (FMV as on 31-Jan-2018) is NOT applied; full gain is
    taxed. This is flagged clearly as a v2 item.
  - LTCG equity exemption threshold (₹1,25,000 aggregate/year) is applied
    as a simple annual reduction, not lot-by-lot.
  - Flat rates used: LTCG 12.5%, STCG 20% (equity, per Budget 2024 regime).

Run: python tax_classifier.py
Reads:  ./data/realized_gains.csv
Writes: ./data/classified_gains.csv, ./data/tax_summary.csv
"""

from pathlib import Path
from typing import Optional

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "backend" / "data"

LTCG_THRESHOLD_DAYS = 365
LTCG_RATE = 0.125
STCG_RATE = 0.20
LTCG_ANNUAL_EXEMPTION_INR = 125_000


def classify(realized: pd.DataFrame) -> pd.DataFrame:
    """Classify each realized gain/loss record as LTCG or STCG.

    Filters to rows with a non-null ``realized_gain_inr``, assigns the
    Indian financial year for each sale, and labels each record as:
    - "LTCG" if ``holding_period_days`` > LTCG_THRESHOLD_DAYS (365)
    - "STCG" otherwise (includes cases where holding period is NaN/None,
      which are conservatively treated as short-term)

    Args:
        realized: DataFrame from FIFO matching with columns including
                  realized_gain_inr, sell_date, holding_period_days.

    Returns:
        Filtered copy of ``realized`` with added columns:
        financial_year (str, e.g. "FY2023-24") and gain_type ("LTCG"/"STCG").
    """
    df = realized[realized["realized_gain_inr"].notna()].copy()
    df["sell_date"] = pd.to_datetime(df["sell_date"])
    df["financial_year"] = df["sell_date"].apply(fy_label)
    df["gain_type"] = df["holding_period_days"].apply(_classify_holding)
    return df


def _classify_holding(days: Optional[float]) -> str:
    """Return 'LTCG' if holding period exceeds threshold, 'STCG' otherwise.

    NaN/None holding periods are conservatively classified as 'STCG' to avoid
    under-reporting tax liability on incomplete data.

    Args:
        days: Holding period in days, or None/NaN if unavailable.

    Returns:
        "LTCG" or "STCG".
    """
    if days is None or (isinstance(days, float) and pd.isna(days)):
        return "STCG"
    return "LTCG" if days > LTCG_THRESHOLD_DAYS else "STCG"


def fy_label(date) -> str:
    """Return Indian financial year label for a given date.

    Indian FY runs from 1 Apr to 31 Mar.  A sale on 2024-01-15 belongs to
    FY2023-24; a sale on 2024-05-01 belongs to FY2024-25.

    Args:
        date: A date-like object with .year and .month attributes.

    Returns:
        String of the form "FY{YYYY}-{YY}", e.g. "FY2023-24".
    """
    # Indian FY: 1 Apr - 31 Mar
    year = date.year if date.month >= 4 else date.year - 1
    return f"FY{year}-{str(year + 1)[-2:]}"


def summarize_tax(classified: pd.DataFrame) -> pd.DataFrame:
    """Aggregate classified gains into a per-FY tax summary.

    Applies the LTCG annual exemption (₹1,25,000 per FY) as a simple annual
    reduction on aggregate LTCG — not lot-by-lot.  STCG losses are NOT offset
    against LTCG gains in this simplified model (v2 item).

    Flat tax rates used (Budget 2024 regime, listed equity):
    - LTCG: 12.5% on taxable amount (after exemption)
    - STCG: 20.0% on positive gains only (negative STCG = carry-forward, not modelled)

    Args:
        classified: DataFrame returned by :func:`classify`, containing columns
                    financial_year, gain_type, realized_gain_inr.

    Returns:
        DataFrame with one row per financial year and columns:
        financial_year, ltcg_gain_inr, stcg_gain_inr,
        ltcg_exemption_applied_inr, taxable_ltcg_inr,
        ltcg_tax_inr, stcg_tax_inr, total_tax_inr.
    """
    rows = []
    for fy, fy_df in classified.groupby("financial_year"):
        ltcg_gain = fy_df.loc[fy_df["gain_type"] == "LTCG", "realized_gain_inr"].sum()
        stcg_gain = fy_df.loc[fy_df["gain_type"] == "STCG", "realized_gain_inr"].sum()

        taxable_ltcg = max(ltcg_gain - LTCG_ANNUAL_EXEMPTION_INR, 0)
        ltcg_tax = round(taxable_ltcg * LTCG_RATE, 2)
        stcg_tax = round(max(stcg_gain, 0) * STCG_RATE, 2)

        rows.append({
            "financial_year": fy,
            "ltcg_gain_inr": round(ltcg_gain, 2),
            "stcg_gain_inr": round(stcg_gain, 2),
            "ltcg_exemption_applied_inr": min(ltcg_gain, LTCG_ANNUAL_EXEMPTION_INR) if ltcg_gain > 0 else 0,
            "taxable_ltcg_inr": round(taxable_ltcg, 2),
            "ltcg_tax_inr": ltcg_tax,
            "stcg_tax_inr": stcg_tax,
            "total_tax_inr": round(ltcg_tax + stcg_tax, 2),
        })
    return pd.DataFrame(rows).sort_values("financial_year")


def main():
    realized = pd.read_csv(DATA_DIR / "realized_gains.csv")
    classified = classify(realized)
    classified.to_csv(DATA_DIR / "classified_gains.csv", index=False)

    summary = summarize_tax(classified)
    summary.to_csv(DATA_DIR / "tax_summary.csv", index=False)

    print(f"Classified {len(classified)} realized gain records")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
