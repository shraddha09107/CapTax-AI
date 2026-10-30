"""
CapTax AI - FIFO Cost-Basis Matching Module
Owner: Anishka Jain (Backend & Data Lead) — reconciliation engine / cost-basis matching

Matches SELL transactions against the earliest available BUY lots per
symbol (First-In-First-Out), producing realized gain/loss records with
holding period, used for LTCG/STCG classification downstream.

Run: python fifo_matcher.py
Reads:  ./data/adjusted_trades.csv
Writes: ./data/realized_gains.csv
"""

from collections import deque
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"


def fifo_match(trades: pd.DataFrame) -> pd.DataFrame:
    """Matches SELL transactions against earliest BUY lots per symbol (FIFO).
    
    Deterministic sorting:
      1. Group by symbol
      2. Order by trade_date ascending
      3. For identical trade dates, prioritize BUY before SELL (side_priority)
         to avoid spurious UNMATCHED_SELL_QUANTITY when buys and sells occur same day.
    """
    if trades.empty:
        return pd.DataFrame()

    trades = trades.copy()
    trades["trade_date"] = pd.to_datetime(trades["trade_date"])
    
    # Prioritize BUY (0) over SELL (1) on identical trade dates
    trades["side_priority"] = trades["transaction_type"].map({"BUY": 0, "SELL": 1}).fillna(2)
    trades = trades.sort_values(["symbol", "trade_date", "side_priority"]).drop(columns=["side_priority"])

    realized: List[Dict[str, Any]] = []
    lots_by_symbol: Dict[str, deque] = {}

    for _, row in trades.iterrows():
        symbol = row["symbol"]
        lots = lots_by_symbol.setdefault(symbol, deque())

        if row["transaction_type"] == "BUY":
            lots.append({
                "date": row["trade_date"],
                "qty": row["adj_quantity"],
                "price": row["adj_price"],
                "broker": row["broker"],
            })
            continue

        # SELL: consume oldest lots first
        qty_to_sell = row["adj_quantity"]
        sell_price = row["adj_price"]
        sell_date = row["trade_date"]

        while qty_to_sell > 0 and lots:
            lot = lots[0]
            matched_qty = min(qty_to_sell, lot["qty"])

            holding_days = (sell_date - lot["date"]).days
            cost_basis = matched_qty * lot["price"]
            sale_value = matched_qty * sell_price

            realized.append({
                "symbol": symbol,
                "broker": row["broker"],
                "buy_date": lot["date"].date(),
                "sell_date": sell_date.date(),
                "quantity": matched_qty,
                "buy_price": round(lot["price"], 2),
                "sell_price": round(sell_price, 2),
                "cost_basis_inr": round(cost_basis, 2),
                "sale_value_inr": round(sale_value, 2),
                "realized_gain_inr": round(sale_value - cost_basis, 2),
                "holding_period_days": holding_days,
            })

            lot["qty"] -= matched_qty
            qty_to_sell -= matched_qty
            if lot["qty"] <= 0:
                lots.popleft()

        if qty_to_sell > 0:
            # Sold more than currently tracked (e.g. pre-existing holding
            # not present in synthetic data) — flag rather than fail.
            realized.append({
                "symbol": symbol,
                "broker": row["broker"],
                "buy_date": None,
                "sell_date": sell_date.date(),
                "quantity": qty_to_sell,
                "buy_price": None,
                "sell_price": round(sell_price, 2),
                "cost_basis_inr": None,
                "sale_value_inr": round(qty_to_sell * sell_price, 2),
                "realized_gain_inr": None,
                "holding_period_days": None,
                "flag": "UNMATCHED_SELL_QUANTITY",
            })

    return pd.DataFrame(realized)


def main():
    adjusted = pd.read_csv(DATA_DIR / "adjusted_trades.csv")
    realized = fifo_match(adjusted)
    out_path = DATA_DIR / "realized_gains.csv"
    realized.to_csv(out_path, index=False)
    matched = realized["realized_gain_inr"].notna().sum() if not realized.empty else 0
    print(f"FIFO-matched {matched} realized gain/loss records")
    print(f"Wrote {out_path} ({len(realized)} rows)")


if __name__ == "__main__":
    main()
