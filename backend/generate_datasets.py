"""
CapTax AI - Synthetic Dataset Generator
Owner: Anishka Jain (Backend & Data Lead)

Generates six broker-format CSVs with intentionally varied column naming
and date formats, simulating real-world multi-broker data ingestion
challenges for Indian capital gains / foreign asset tax disclosure.

Sources:
  1. Zerodha        (equity/MF trade contract-note style export)
  2. Groww          (equity/MF trade export)
  3. ICICI Direct   (equity trade export)
  4. Interactive Brokers (US equity/ETF export - for foreign asset/Schedule FA)
  5. Corporate Actions (splits, bonuses, dividends affecting cost basis)
  6. Foreign Dividends (for DTAA relief / Schedule FSI computation)

Reproducibility:
  Both ``random`` and ``numpy.random`` are seeded with 42 at module load time.
  Re-running this script always produces the same CSVs, making the synthetic
  dataset deterministic and safe to use in automated tests and demos.

Output column naming is deliberately inconsistent across brokers to exercise
the normalisation logic in ``ingest.py``.

Run: python generate_datasets.py
Output: ./data/*.csv
"""

import random
import datetime as dt
from pathlib import Path
import pandas as pd
import numpy as np

random.seed(42)       # Seed stdlib random for reproducible data generation
np.random.seed(42)    # Seed numpy random independently (some generators use np.random)

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)

INDIAN_STOCKS = [
    ("RELIANCE", "Reliance Industries Ltd"),
    ("TCS", "Tata Consultancy Services Ltd"),
    ("INFY", "Infosys Ltd"),
    ("HDFCBANK", "HDFC Bank Ltd"),
    ("ICICIBANK", "ICICI Bank Ltd"),
    ("SBIN", "State Bank of India"),
    ("ITC", "ITC Ltd"),
    ("LT", "Larsen & Toubro Ltd"),
    ("BHARTIARTL", "Bharti Airtel Ltd"),
    ("HINDUNILVR", "Hindustan Unilever Ltd"),
    ("TATAMOTORS", "Tata Motors Ltd"),
    ("WIPRO", "Wipro Ltd"),
]

US_STOCKS = [
    ("AAPL", "Apple Inc"),
    ("MSFT", "Microsoft Corp"),
    ("GOOGL", "Alphabet Inc Class A"),
    ("AMZN", "Amazon.com Inc"),
    ("NVDA", "NVIDIA Corp"),
    ("TSLA", "Tesla Inc"),
    ("META", "Meta Platforms Inc"),
]

def random_date(start, end):
    """Return a random date between *start* (inclusive) and *end* (inclusive)."""
    delta = end - start
    return start + dt.timedelta(days=random.randint(0, delta.days))

# Date range covering FY2022-23, FY2023-24, and FY2024-25 (1 Apr 2022 – 31 Mar 2025)
FY_START = dt.date(2022, 4, 1)
FY_END   = dt.date(2025, 3, 31)


def gen_zerodha(n=180):
    """Zerodha contract-note style export."""
    rows = []
    for i in range(n):
        sym, name = random.choice(INDIAN_STOCKS)
        trade_date = random_date(FY_START, FY_END)
        side = random.choice(["buy", "sell"])
        qty = random.randint(1, 500)
        price = round(random.uniform(50, 4000), 2)
        rows.append({
            "Symbol": sym,
            "ISIN": f"INE{random.randint(100000,999999)}A01{random.randint(10,99)}",
            "Trade Date": trade_date.strftime("%Y-%m-%d"),
            "Trade Type": side,
            "Quantity": qty,
            "Price": price,
            "Trade ID": f"ZD{100000+i}",
            "Order ID": f"ORD{200000+i}",
            "Exchange": random.choice(["NSE", "BSE"]),
            "Brokerage": round(price * qty * 0.0003, 2),
            "STT": round(price * qty * 0.001, 2),
            "Segment": "EQ",
        })
    return pd.DataFrame(rows)


def gen_groww(n=150):
    """Groww export - different column naming and date format (DD/MM/YYYY)."""
    rows = []
    for i in range(n):
        sym, name = random.choice(INDIAN_STOCKS)
        trade_date = random_date(FY_START, FY_END)
        side = random.choice(["BUY", "SELL"])
        qty = random.randint(1, 300)
        price = round(random.uniform(50, 4000), 2)
        rows.append({
            "Stock Name": name,
            "Ticker": sym,
            "Date": trade_date.strftime("%d/%m/%Y"),
            "Txn Type": side,
            "Qty": qty,
            "Avg Price": price,
            "Order Ref": f"GRW-{300000+i}",
            "Total Amount": round(price * qty, 2),
            "Exchange Segment": random.choice(["NSE", "BSE"]),
            "Charges": round(price * qty * 0.00025, 2),
        })
    return pd.DataFrame(rows)


def gen_icici_direct(n=120):
    """ICICI Direct export - yet another naming/date convention."""
    rows = []
    for i in range(n):
        sym, name = random.choice(INDIAN_STOCKS)
        trade_date = random_date(FY_START, FY_END)
        side = random.choice(["B", "S"])
        qty = random.randint(1, 400)
        price = round(random.uniform(50, 4000), 2)
        rows.append({
            "Scrip Code": sym,
            "Company Name": name,
            "Execution Date": trade_date.strftime("%d-%b-%Y"),
            "B/S Indicator": side,
            "Quantity Traded": qty,
            "Rate": price,
            "Contract Note No": f"ICD{400000+i}",
            "Net Amount": round(price * qty, 2),
            "Exchange": random.choice(["NSE", "BSE"]),
            "Transaction Charges": round(price * qty * 0.0004, 2),
        })
    return pd.DataFrame(rows)


def gen_interactive_brokers(n=90):
    """Interactive Brokers export - US equities, relevant to Schedule FA/FSI."""
    rows = []
    for i in range(n):
        sym, name = random.choice(US_STOCKS)
        trade_date = random_date(FY_START, FY_END)
        side = random.choice(["BUY", "SELL"])
        qty = random.randint(1, 100)
        price = round(random.uniform(50, 900), 2)
        fx_rate = round(random.uniform(78, 87), 2)  # USD-INR
        rows.append({
            "Symbol": sym,
            "Description": name,
            "TradeDate": trade_date.strftime("%Y%m%d"),
            "Buy/Sell": side,
            "Quantity": qty,
            "TradePrice": price,
            "Currency": "USD",
            "FXRateToINR": fx_rate,
            "TransactionID": f"IB{500000+i}",
            "Commission": round(price * qty * 0.0005, 2),
            "Exchange": random.choice(["NASDAQ", "NYSE"]),
        })
    return pd.DataFrame(rows)


def gen_corporate_actions(n=25):
    """Corporate actions affecting cost-basis adjustment (splits, bonuses, dividends)."""
    rows = []
    action_types = ["Split", "Bonus", "Dividend", "Rights"]
    all_stocks = INDIAN_STOCKS + US_STOCKS
    for i in range(n):
        sym, name = random.choice(all_stocks)
        action = random.choice(action_types)
        ex_date = random_date(FY_START, FY_END)
        if action == "Split":
            ratio = random.choice(["1:2", "1:5", "1:10"])
            detail = f"Stock split {ratio}"
        elif action == "Bonus":
            ratio = random.choice(["1:1", "2:1", "1:2"])
            detail = f"Bonus issue {ratio}"
        elif action == "Rights":
            ratio = random.choice(["1:4", "1:5"])
            detail = f"Rights issue {ratio}"
        else:
            ratio = ""
            detail = f"Dividend INR {round(random.uniform(1,50),2)}/share"
        rows.append({
            "Ticker/Symbol": sym,
            "Company": name,
            "Action Type": action,
            "Ex-Date": ex_date.strftime("%Y-%m-%d"),
            "Ratio/Detail": detail,
            "Record Date": (ex_date + dt.timedelta(days=2)).strftime("%Y-%m-%d"),
            "Market": "NSE/BSE" if (sym, name) in INDIAN_STOCKS else "US",
        })
    return pd.DataFrame(rows)


def gen_foreign_dividends(n=40):
    """Foreign dividend income for DTAA relief / Schedule FSI computation."""
    rows = []
    for i in range(n):
        sym, name = random.choice(US_STOCKS)
        pay_date = random_date(FY_START, FY_END)
        gross_usd = round(random.uniform(5, 500), 2)
        wht_rate = 0.25  # US withholding tax rate under India-US DTAA
        wht_usd = round(gross_usd * wht_rate, 2)
        fx_rate = round(random.uniform(78, 87), 2)
        rows.append({
            "Security": f"{sym} - {name}",
            "Payment Date": pay_date.strftime("%m/%d/%Y"),
            "Gross Dividend (USD)": gross_usd,
            "Withholding Tax (USD)": wht_usd,
            "Net Dividend (USD)": round(gross_usd - wht_usd, 2),
            "Country of Source": "USA",
            "USD-INR Rate": fx_rate,
            "DTAA Article": "10(2)",
            "TDS Certificate Ref": f"1042S-{600000+i}",
        })
    return pd.DataFrame(rows)


def main():
    """Generate all six synthetic CSV datasets and write them to ./data/.

    Prints a per-file summary (filename, row count, column names) and a
    grand total of rows written.  All files are overwritten on each run,
    so the output is always deterministic given the fixed random seed.
    """
    datasets = {
        "zerodha_trades.csv": gen_zerodha(),
        "groww_trades.csv": gen_groww(),
        "icici_direct_trades.csv": gen_icici_direct(),
        "interactive_brokers_trades.csv": gen_interactive_brokers(),
        "corporate_actions.csv": gen_corporate_actions(),
        "foreign_dividends.csv": gen_foreign_dividends(),
    }
    total_rows = 0
    for fname, df in datasets.items():
        path = OUT_DIR / fname
        df.to_csv(path, index=False)
        print(f"Generated {fname}: {len(df)} rows, columns={list(df.columns)}")
        total_rows += len(df)
    print(f"\nTotal rows written across {len(datasets)} files: {total_rows}")


if __name__ == "__main__":
    main()
