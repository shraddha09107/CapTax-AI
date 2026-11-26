"""
CapTax AI - Corporate Action Adjustment Module
Owner: Anishka Jain (Backend & Data Lead) — reconciliation engine / corporate action & FX logic

Adjusts pre-existing BUY lots for splits and bonus issues so that FIFO
matching downstream works on split/bonus-adjusted quantity and cost basis.
Dividends and rights issues are logged for reference but do not alter
existing lot quantity/cost (dividends are separate taxable income; rights
issue application is treated as a fresh purchase, out of scope for v1).

Run: python corporate_actions_adjuster.py
Reads:  ./data/normalized_trades.csv, ./data/corporate_actions.csv
Writes: ./data/adjusted_trades.csv
"""

import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

logger = logging.getLogger(__name__)


def parse_ratio(detail: str) -> Optional[float]:
    """Extract a numeric multiplier from a split/bonus ratio string like '1:2' or '2:1'.

    Interpretation:
      - Split "1:2" → 1 old share becomes 2 new shares → multiplier = 2.0
      - Bonus "1:1" → 1 original + 1 bonus = 2 shares held → multiplier = 2.0
      - Returns None if the ratio string cannot be parsed or produces a zero denominator.

    Args:
        detail: Free-text ratio/detail string from corporate actions data,
                e.g. "Stock split 1:2", "Bonus issue 1:1".

    Returns:
        float multiplier to apply to pre-ex-date BUY quantities, or None on failure.
    """
    match = re.search(r"(\d+)\s*:\s*(\d+)", detail)
    if not match:
        return None
    old, new = int(match.group(1)), int(match.group(2))
    # Guard against zero denominator (e.g. malformed "0:2" ratios)
    if old == 0:
        logger.warning("parse_ratio: zero denominator in '%s' — skipping", detail)
        return None
    # "old : new" means: for every `old` shares held, you now have `new` shares (bonus/split),
    # e.g. Split "1:2" -> 1 share becomes 2 -> multiplier 2
    # e.g. Bonus "1:1" -> 1 share becomes 2 (1 original + 1 bonus) -> multiplier 2
    return new / old if "split" in detail.lower() else (old + new) / old


def load_actions() -> pd.DataFrame:
    """Load and parse the corporate actions CSV, converting Ex-Date to datetime."""
    df = pd.read_csv(DATA_DIR / "corporate_actions.csv")
    df["Ex-Date"] = pd.to_datetime(df["Ex-Date"])
    return df


def apply_adjustments(trades: pd.DataFrame, actions: pd.DataFrame) -> pd.DataFrame:
    """Adjust pre-ex-date BUY lots for corporate actions (splits and bonus issues).

    For each Split or Bonus action, any BUY trade for the affected symbol dated
    strictly before the ex-date has its quantity multiplied and price divided by
    the computed multiplier. This preserves total cost basis while reflecting the
    post-action share count, ensuring downstream FIFO matching is correct.

    Dividends and Rights issues in ``actions`` are intentionally skipped:
    - Dividends are treated as separate taxable income (not a lot adjustment).
    - Rights issue applications are fresh purchases, out of scope for v1.

    Args:
        trades:  DataFrame of normalized trades (must include columns: symbol,
                 transaction_type, trade_date, quantity, price_inr).
        actions: DataFrame of corporate actions (must include: Ticker/Symbol,
                 Action Type, Ex-Date, Ratio/Detail).

    Returns:
        Copy of ``trades`` with additional columns: adj_quantity, adj_price,
        adjustment_note (semicolon-separated log of applied actions per lot).
    """
    # Guard: nothing to do if either DataFrame is empty
    if trades.empty or actions.empty:
        logger.info("apply_adjustments: empty input — returning trades unchanged")
        trades = trades.copy()
        trades["adj_quantity"] = trades.get("quantity", pd.Series(dtype="int64"))
        trades["adj_price"] = trades.get("price_inr", pd.Series(dtype="float64"))
        trades["adjustment_note"] = ""
        return trades

    trades = trades.copy()
    trades["trade_date"] = pd.to_datetime(trades["trade_date"])
    trades["adj_quantity"] = trades["quantity"]
    trades["adj_price"] = trades["price_inr"]
    trades["adjustment_note"] = ""

    relevant = actions[actions["Action Type"].isin(["Split", "Bonus"])]

    for _, action in relevant.iterrows():
        symbol = action["Ticker/Symbol"]
        ex_date = action["Ex-Date"]
        multiplier = parse_ratio(action["Ratio/Detail"])
        if multiplier is None:
            continue

        # Any BUY lot for this symbol dated before the ex-date gets its
        # quantity multiplied and price divided (cost basis preserved).
        mask = (
            (trades["symbol"] == symbol)
            & (trades["transaction_type"] == "BUY")
            & (trades["trade_date"] < ex_date)
        )
        trades.loc[mask, "adj_price"] = trades.loc[mask, "adj_price"] / multiplier
        trades.loc[mask, "adj_quantity"] = (trades.loc[mask, "adj_quantity"] * multiplier).round().astype(int)
        note = f"{action['Action Type']} {action['Ratio/Detail']} on {ex_date.date()}"
        trades.loc[mask, "adjustment_note"] = trades.loc[mask, "adjustment_note"] + note + "; "

    return trades


def main():
    trades = pd.read_csv(DATA_DIR / "normalized_trades.csv")
    actions = load_actions()
    adjusted = apply_adjustments(trades, actions)
    out_path = DATA_DIR / "adjusted_trades.csv"
    adjusted.to_csv(out_path, index=False)
    n_adjusted = (adjusted["adjustment_note"] != "").sum()
    print(f"Applied corporate action adjustments to {n_adjusted} lots")
    print(f"Wrote {out_path} ({len(adjusted)} rows)")


if __name__ == "__main__":
    main()
