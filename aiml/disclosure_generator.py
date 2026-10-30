"""
CapTax AI - Disclosure Report Generator (Schedule CG / FA / FSI summary)
Owner: Shraddha Singh (Team Lead & AI/Interpretation Lead) — disclosure synthesis
(the frontend rendering of this report — "disclosure preview UI" — is Akash's, see frontend/index.html)

Assembles final outputs from the tax classification and DTAA relief steps
into a single, human-readable disclosure summary — a simplified stand-in
for the ITR Schedule CG (Capital Gains), Schedule FA (Foreign Assets) and
Schedule FSI (Foreign Source Income) sections.

Run: python disclosure_generator.py
Reads:  ./data/tax_summary.csv, ./data/dtaa_relief.csv,
        ./data/interactive_brokers_trades.csv (for Schedule FA holdings)
Writes: ./data/disclosure_summary.txt
"""

from pathlib import Path
from typing import List
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "backend" / "data"


def build_schedule_fa(ib_trades: pd.DataFrame) -> pd.DataFrame:
    """Simplified Schedule FA: list of foreign equity holdings ever traded (peak qty proxy)."""
    ib_trades = ib_trades.copy()
    ib_trades["signed_qty"] = ib_trades["Quantity"] * ib_trades["Buy/Sell"].map({"BUY": 1, "SELL": -1})
    holdings = ib_trades.groupby(["Symbol", "Description"])["signed_qty"].sum().reset_index()
    holdings = holdings[holdings["signed_qty"] > 0].rename(columns={"signed_qty": "net_holding_units"})
    return holdings


def render_report(tax_summary: pd.DataFrame, dtaa: pd.DataFrame, fa_holdings: pd.DataFrame) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("CapTax AI — Simplified Tax Disclosure Summary")
    lines.append("(Academic prototype — not a substitute for filed ITR schedules)")
    lines.append("=" * 70)

    lines.append("\n--- Schedule CG: Capital Gains (Indian equity, FIFO-matched) ---")
    if tax_summary.empty:
        lines.append("No realized capital gains found.")
    else:
        for _, row in tax_summary.iterrows():
            lines.append(f"\n{row['financial_year']}")
            lines.append(f"  LTCG (gain before exemption): Rs. {row['ltcg_gain_inr']:,}")
            lines.append(f"  LTCG exemption applied:       Rs. {row['ltcg_exemption_applied_inr']:,}")
            lines.append(f"  Taxable LTCG:                 Rs. {row['taxable_ltcg_inr']:,}  @ 12.5% -> Rs. {row['ltcg_tax_inr']:,}")
            lines.append(f"  STCG (taxable):                Rs. {row['stcg_gain_inr']:,}  @ 20%   -> Rs. {row['stcg_tax_inr']:,}")
            lines.append(f"  Total capital gains tax:       Rs. {row['total_tax_inr']:,}")

    lines.append("\n--- Schedule FSI: Foreign Source Income & DTAA Relief ---")
    if dtaa.empty:
        lines.append("No foreign dividend income found.")
    else:
        by_fy = dtaa.groupby("financial_year")[
            ["gross_dividend_inr", "foreign_tax_withheld_inr", "dtaa_relief_inr", "net_indian_tax_payable_inr"]
        ].sum().round(2)
        for fy, row in by_fy.iterrows():
            lines.append(f"\n{fy}")
            lines.append(f"  Gross foreign dividend income: Rs. {row['gross_dividend_inr']:,}")
            lines.append(f"  Tax withheld abroad (US):      Rs. {row['foreign_tax_withheld_inr']:,}")
            lines.append(f"  DTAA relief (Sec 90, Art 25):  Rs. {row['dtaa_relief_inr']:,}")
            lines.append(f"  Net Indian tax payable:        Rs. {row['net_indian_tax_payable_inr']:,}")

    lines.append("\n--- Schedule FA: Foreign Assets Held (US equity, net positive holdings) ---")
    if fa_holdings.empty:
        lines.append("No foreign equity holdings found.")
    else:
        for _, row in fa_holdings.iterrows():
            lines.append(f"  {row['Symbol']:<8} {row['Description']:<25} net holding: {row['net_holding_units']:.0f} units")

    lines.append("\n" + "=" * 70)
    lines.append("NOTE: Grandfathering (31-Jan-2018 FMV) not yet applied — see v2 backlog.")
    lines.append("=" * 70)
    return "\n".join(lines)


def main():
    tax_summary = pd.read_csv(DATA_DIR / "tax_summary.csv")
    dtaa = pd.read_csv(DATA_DIR / "dtaa_relief.csv")
    ib_trades = pd.read_csv(DATA_DIR / "interactive_brokers_trades.csv")

    fa_holdings = build_schedule_fa(ib_trades)
    report = render_report(tax_summary, dtaa, fa_holdings)

    out_path = DATA_DIR / "disclosure_summary.txt"
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
