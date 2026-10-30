# 04. Exhaustive File-by-File Source Code Extraction & Technical Walkthrough

> **Module Focus:** Complete Source Code of `Backend_data`  
> **Author & Mentor:** Senior Backend Developer & Technical Mentor  
> **Rule:** Every single line of backend code is extracted verbatim and explained block by block.

---

## 1. File: `backend/app.py`

### 1.1 Complete Verbatim Source Code

```python
"""
CapTax AI - Backend API
Owner: Anishka Jain (Backend & Data Lead)

FastAPI app that wraps the ingestion -> FIFO -> classification -> DTAA ->
disclosure pipeline and exposes it over HTTP for the frontend dashboard.

Run: uvicorn app:app --reload --port 8000   (from inside backend/)
Docs: http://localhost:8000/docs
"""

import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
AIML_DIR = PROJECT_DIR / "aiml"
DATA_DIR = BACKEND_DIR / "data"

app = FastAPI(title="CapTax AI API", version="0.1.0")

# Allow the frontend (served separately, e.g. via a dev server) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PIPELINE = [
    (BACKEND_DIR / "generate_datasets.py", "Anishka Jain"),
    (BACKEND_DIR / "ingest.py", "Anishka Jain"),
    (BACKEND_DIR / "corporate_actions_adjuster.py", "Anishka Jain"),
    (BACKEND_DIR / "fifo_matcher.py", "Anishka Jain"),
    (AIML_DIR / "tax_classifier.py", "Shraddha Singh"),
    (AIML_DIR / "dtaa_relief.py", "Shraddha Singh"),
    (AIML_DIR / "disclosure_generator.py", "Shraddha Singh"),
]


def _run_script(script_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=script_path.parent,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"{script_path.name} failed:\n{result.stdout}\n{result.stderr}",
        )


def _read_csv_as_records(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found — run /pipeline/run first")
    df = pd.read_csv(path)
    return df.fillna("").to_dict(orient="records")


@app.get("/")
def root():
    return {"service": "CapTax AI API", "status": "ok", "endpoints": [
        "/pipeline/run", "/data/trades", "/data/tax-summary",
        "/data/dtaa-relief", "/data/disclosure-summary",
    ]}


@app.post("/pipeline/run")
def run_pipeline():
    """Runs every stage of the pipeline in order and returns a step log."""
    log = []
    for script_path, owner in PIPELINE:
        _run_script(script_path)
        log.append({"step": script_path.name, "owner": owner, "status": "completed"})
    return {"status": "completed", "steps": log}


@app.get("/data/trades")
def get_trades():
    return _read_csv_as_records("normalized_trades.csv")


@app.get("/data/realized-gains")
def get_realized_gains():
    return _read_csv_as_records("realized_gains.csv")


@app.get("/data/tax-summary")
def get_tax_summary():
    return _read_csv_as_records("tax_summary.csv")


@app.get("/data/dtaa-relief")
def get_dtaa_relief():
    return _read_csv_as_records("dtaa_relief.csv")


@app.get("/data/disclosure-summary")
def get_disclosure_summary():
    path = DATA_DIR / "disclosure_summary.txt"
    if not path.exists():
        raise HTTPException(status_code=404, detail="disclosure_summary.txt not found — run /pipeline/run first")
    return {"report": path.read_text()}
```

### 1.2 Detailed Block-by-Block Explanation of `app.py`

#### Lines 1–10: Module Header & Documentation
```python
"""
CapTax AI - Backend API
Owner: Anishka Jain (Backend & Data Lead)
...
"""
```
- **Explanation:** Docstring indicating authorship, module purpose, startup command, and OpenAPI URL.

#### Lines 12–18: Imports & Dependencies
- `import subprocess`: Standard library module used to spawn new OS processes, connect to pipes, and capture return codes. Required for running external pipeline scripts.
- `import sys`: Used to locate the currently executing Python binary (`sys.executable`) to ensure child scripts run with the identical virtual environment interpreter.
- `from pathlib import Path`: Object-oriented filesystem path manipulation.
- `from fastapi import FastAPI, HTTPException`: `FastAPI` is the core ASGI application class; `HTTPException` is used to halt request processing and return custom HTTP error status codes and JSON payloads.
- `from fastapi.middleware.cors import CORSMiddleware`: Starlette middleware used to handle Cross-Origin Resource Sharing preflight `OPTIONS` requests and response headers.
- `import pandas as pd`: Utilized here to read generated CSV outputs from disk and convert them into dictionaries.

#### Lines 20–24: Path Resolutions
```python
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
AIML_DIR = PROJECT_DIR / "aiml"
DATA_DIR = BACKEND_DIR / "data"
```
- `BACKEND_DIR`: Absolute path to `Backend_data/backend`.
- `PROJECT_DIR`: Points to `Backend_data`.
- `AIML_DIR`: Resolves to `Backend_data/aiml` (Note: In the multi-branch folder setup, the actual AI scripts reside at `d:\CapTax-AI\AIML\aiml`; see Section 10 for the bug and fix).
- `DATA_DIR`: Resolves to `Backend_data/backend/data`.

#### Lines 25–33: Application Instantiation & CORS Configuration
```python
app = FastAPI(title="CapTax AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```
- Configures CORS with wildcard `["*"]`. This allows browser clients loaded from `file://` or `http://localhost:5500` (e.g., Live Server) to make cross-origin requests to `http://localhost:8000` without triggering browser security blocks.

#### Lines 35–43: Pipeline Execution Registry
```python
PIPELINE = [
    (BACKEND_DIR / "generate_datasets.py", "Anishka Jain"),
    (BACKEND_DIR / "ingest.py", "Anishka Jain"),
    (BACKEND_DIR / "corporate_actions_adjuster.py", "Anishka Jain"),
    (BACKEND_DIR / "fifo_matcher.py", "Anishka Jain"),
    (AIML_DIR / "tax_classifier.py", "Shraddha Singh"),
    (AIML_DIR / "dtaa_relief.py", "Shraddha Singh"),
    (AIML_DIR / "disclosure_generator.py", "Shraddha Singh"),
]
```
- An ordered list of tuples defining the linear ETL workflow. Each tuple stores the absolute path to the Python script and the team member responsible. The order of execution is critical: Data Generation $\rightarrow$ Ingestion $\rightarrow$ Corporate Action Adjustment $\rightarrow$ FIFO Matching $\rightarrow$ Tax Classification $\rightarrow$ DTAA Relief $\rightarrow$ Final Disclosure Synthesis.

#### Lines 46–57: Helper Function `_run_script`
```python
def _run_script(script_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=script_path.parent,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"{script_path.name} failed:\n{result.stdout}\n{result.stderr}",
        )
```
- **Input:** `script_path` (`Path` object representing the script to execute).
- **Behavior:** Executes `python <script>` synchronously. Sets working directory (`cwd`) to the script's parent folder. Captures standard output and standard error as strings (`text=True`).
- **Error Handling:** If `result.returncode != 0`, raises an HTTP 500 error containing the exact stdout and stderr traces from the failed script.
- **Return Value:** `None`.

#### Lines 60–65: Helper Function `_read_csv_as_records`
```python
def _read_csv_as_records(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found — run /pipeline/run first")
    df = pd.read_csv(path)
    return df.fillna("").to_dict(orient="records")
```
- **Input:** `filename` (`str`, e.g., `"normalized_trades.csv"`).
- **Behavior:** Verifies the file exists on disk. If absent, raises HTTP 404 informing the caller to execute `/pipeline/run` first. If present, loads the CSV into a DataFrame, replaces missing `NaN` values with empty strings (preventing invalid JSON `NaN` serialization), and converts rows into a list of dictionaries (`to_dict(orient="records")`).
- **Return Value:** `List[Dict[str, Any]]`.

---

### 1.3 Detailed API Endpoint Specifications in `app.py`

#### 1. `GET /`
- **Purpose:** Health check and root service discovery.
- **Request Parameters / Body:** None.
- **Response Structure (200 OK):**
  ```json
  {
    "service": "CapTax AI API",
    "status": "ok",
    "endpoints": [
      "/pipeline/run",
      "/data/trades",
      "/data/tax-summary",
      "/data/dtaa-relief",
      "/data/disclosure-summary"
    ]
  }
  ```
- **Error Handling:** None (always returns 200).
- **Auth:** None.

#### 2. `POST /pipeline/run`
- **Purpose:** Triggers the end-to-end execution of all 7 pipeline stages sequentially.
- **Request Parameters / Body:** None.
- **Response Structure (200 OK):**
  ```json
  {
    "status": "completed",
    "steps": [
      {"step": "generate_datasets.py", "owner": "Anishka Jain", "status": "completed"},
      {"step": "ingest.py", "owner": "Anishka Jain", "status": "completed"},
      {"step": "corporate_actions_adjuster.py", "owner": "Anishka Jain", "status": "completed"},
      {"step": "fifo_matcher.py", "owner": "Anishka Jain", "status": "completed"},
      {"step": "tax_classifier.py", "owner": "Shraddha Singh", "status": "completed"},
      {"step": "dtaa_relief.py", "owner": "Shraddha Singh", "status": "completed"},
      {"step": "disclosure_generator.py", "owner": "Shraddha Singh", "status": "completed"}
    ]
  }
  ```
- **Error Handling:** Returns `500 Internal Server Error` if any script exits with a non-zero exit code or cannot be found.
- **Auth:** None.

#### 3. `GET /data/trades`
- **Purpose:** Fetches the full list of canonical, normalized trades across all brokers.
- **Request Parameters / Body:** None.
- **Response Structure (200 OK):** Array of objects adhering to the canonical schema:
  ```json
  [
    {
      "broker": "Zerodha",
      "symbol": "INFY",
      "company_name": "",
      "isin": "INE009A01021",
      "trade_date": "2023-05-14",
      "transaction_type": "BUY",
      "quantity": 50,
      "price": 1420.5,
      "price_currency": "INR",
      "fx_rate_to_inr": 1.0,
      "price_inr": 1420.5,
      "gross_amount_inr": 71025.0,
      "charges_inr": 92.33,
      "exchange": "NSE",
      "source_ref": "ZD100045"
    }
  ]
  ```
- **Error Handling:** Returns `404 Not Found` if `normalized_trades.csv` has not yet been generated.
- **Auth:** None.

#### 4. `GET /data/realized-gains`
- **Purpose:** Fetches FIFO cost-basis matched records showing buy/sell matching, holding days, and realized gain/loss.
- **Request Parameters / Body:** None.
- **Response Structure (200 OK):**
  ```json
  [
    {
      "symbol": "TCS",
      "broker": "Groww",
      "buy_date": "2022-08-10",
      "sell_date": "2024-01-15",
      "quantity": 25,
      "buy_price": 3100.0,
      "sell_price": 3800.0,
      "cost_basis_inr": 77500.0,
      "sale_value_inr": 95000.0,
      "realized_gain_inr": 17500.0,
      "holding_period_days": 523
    }
  ]
  ```
- **Error Handling:** Returns `404 Not Found` if `realized_gains.csv` is missing.
- **Auth:** None.

#### 5. `GET /data/tax-summary`
- **Purpose:** Fetches fiscal-year aggregated capital gains tax liability (LTCG, STCG, ₹1.25L exemption, final tax).
- **Request Parameters / Body:** None.
- **Response Structure (200 OK):**
  ```json
  [
    {
      "financial_year": "FY2023-24",
      "ltcg_gain_inr": 210000.0,
      "stcg_gain_inr": 45000.0,
      "ltcg_exemption_applied_inr": 125000.0,
      "taxable_ltcg_inr": 85000.0,
      "ltcg_tax_inr": 10625.0,
      "stcg_tax_inr": 9000.0,
      "total_tax_inr": 19625.0
    }
  ]
  ```
- **Error Handling:** Returns `404 Not Found` if `tax_summary.csv` is missing.
- **Auth:** None.

#### 6. `GET /data/dtaa-relief`
- **Purpose:** Fetches computed foreign dividend income, US withholding tax, and Section 90 DTAA relief.
- **Request Parameters / Body:** None.
- **Response Structure (200 OK):**
  ```json
  [
    {
      "Security": "AAPL - Apple Inc",
      "financial_year": "FY2023-24",
      "Country of Source": "USA",
      "DTAA Article": "10(2)",
      "gross_dividend_inr": 12500.0,
      "foreign_tax_withheld_inr": 3125.0,
      "indian_tax_on_income_inr": 3750.0,
      "dtaa_relief_inr": 3125.0,
      "net_indian_tax_payable_inr": 625.0,
      "TDS Certificate Ref": "1042S-600012"
    }
  ]
  ```
- **Error Handling:** Returns `404 Not Found` if `dtaa_relief.csv` is missing.
- **Auth:** None.

#### 7. `GET /data/disclosure-summary`
- **Purpose:** Returns the complete preformatted text disclosure statement for ITR Schedules CG, FA, and FSI.
- **Request Parameters / Body:** None.
- **Response Structure (200 OK):**
  ```json
  {
    "report": "======================================================================\nCapTax AI — Simplified Tax Disclosure Summary\n..."
  }
  ```
- **Error Handling:** Returns `404 Not Found` if `disclosure_summary.txt` is missing.
- **Auth:** None.

---

## 2. File: `backend/ingest.py`

### 2.1 Complete Verbatim Source Code

```python
"""
CapTax AI - Data Ingestion & Normalization Module (Week 3)
Owner: Anishka Jain (Backend & Data Lead) — broker adapters

Reads the six raw broker-format exports and normalizes them into a single
unified trade schema, resolving:
  - Varied column names across brokers
  - Varied date formats (YYYY-MM-DD, DD/MM/YYYY, DD-Mon-YYYY, YYYYMMDD, MM/DD/YYYY)
  - Varied buy/sell notation (buy/sell, BUY/SELL, B/S, Buy/Sell)
  - Foreign currency trades (Interactive Brokers) converted to INR using
    the provided FX rate, with original currency/amount retained for audit

Unified schema (per trade row):
    broker, symbol, company_name, isin, trade_date, transaction_type,
    quantity, price, price_currency, fx_rate_to_inr, price_inr,
    gross_amount_inr, charges_inr, exchange, source_ref

Run: python ingest.py
Reads:  ./data/*.csv
Writes: ./data/normalized_trades.csv
"""

from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

UNIFIED_COLUMNS = [
    "broker", "symbol", "company_name", "isin", "trade_date",
    "transaction_type", "quantity", "price", "price_currency",
    "fx_rate_to_inr", "price_inr", "gross_amount_inr", "charges_inr",
    "exchange", "source_ref",
]


def _std_side(value: str) -> str:
    """Normalize buy/sell notation to 'BUY' / 'SELL'."""
    v = str(value).strip().upper()
    if v in ("BUY", "B"):
        return "BUY"
    if v in ("SELL", "S"):
        return "SELL"
    raise ValueError(f"Unrecognized transaction side: {value!r}")


def load_zerodha() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "zerodha_trades.csv")
    out = pd.DataFrame({
        "broker": "Zerodha",
        "symbol": df["Symbol"],
        "company_name": pd.NA,
        "isin": df["ISIN"],
        "trade_date": pd.to_datetime(df["Trade Date"], format="%Y-%m-%d"),
        "transaction_type": df["Trade Type"].apply(_std_side),
        "quantity": df["Quantity"].astype(int),
        "price": df["Price"].astype(float),
        "price_currency": "INR",
        "fx_rate_to_inr": 1.0,
        "charges_inr": (df["Brokerage"] + df["STT"]).astype(float),
        "exchange": df["Exchange"],
        "source_ref": df["Trade ID"],
    })
    return out


def load_groww() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "groww_trades.csv")
    out = pd.DataFrame({
        "broker": "Groww",
        "symbol": df["Ticker"],
        "company_name": df["Stock Name"],
        "isin": pd.NA,
        "trade_date": pd.to_datetime(df["Date"], format="%d/%m/%Y"),
        "transaction_type": df["Txn Type"].apply(_std_side),
        "quantity": df["Qty"].astype(int),
        "price": df["Avg Price"].astype(float),
        "price_currency": "INR",
        "fx_rate_to_inr": 1.0,
        "charges_inr": df["Charges"].astype(float),
        "exchange": df["Exchange Segment"],
        "source_ref": df["Order Ref"],
    })
    return out


def load_icici_direct() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "icici_direct_trades.csv")
    out = pd.DataFrame({
        "broker": "ICICI Direct",
        "symbol": df["Scrip Code"],
        "company_name": df["Company Name"],
        "isin": pd.NA,
        "trade_date": pd.to_datetime(df["Execution Date"], format="%d-%b-%Y"),
        "transaction_type": df["B/S Indicator"].apply(_std_side),
        "quantity": df["Quantity Traded"].astype(int),
        "price": df["Rate"].astype(float),
        "price_currency": "INR",
        "fx_rate_to_inr": 1.0,
        "charges_inr": df["Transaction Charges"].astype(float),
        "exchange": df["Exchange"],
        "source_ref": df["Contract Note No"],
    })
    return out


def load_interactive_brokers() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "interactive_brokers_trades.csv")
    out = pd.DataFrame({
        "broker": "Interactive Brokers",
        "symbol": df["Symbol"],
        "company_name": df["Description"],
        "isin": pd.NA,
        "trade_date": pd.to_datetime(df["TradeDate"], format="%Y%m%d"),
        "transaction_type": df["Buy/Sell"].apply(_std_side),
        "quantity": df["Quantity"].astype(int),
        "price": df["TradePrice"].astype(float),
        "price_currency": df["Currency"],
        "fx_rate_to_inr": df["FXRateToINR"].astype(float),
        "charges_inr": (df["Commission"] * df["FXRateToINR"]).astype(float),
        "exchange": df["Exchange"],
        "source_ref": df["TransactionID"],
    })
    return out


LOADERS = {
    "zerodha": load_zerodha,
    "groww": load_groww,
    "icici_direct": load_icici_direct,
    "interactive_brokers": load_interactive_brokers,
}


def normalize_all() -> pd.DataFrame:
    frames = [loader() for loader in LOADERS.values()]
    combined = pd.concat(frames, ignore_index=True)

    # Derived fields
    combined["price_inr"] = (combined["price"] * combined["fx_rate_to_inr"]).round(2)
    combined["gross_amount_inr"] = (combined["price_inr"] * combined["quantity"]).round(2)
    combined["charges_inr"] = combined["charges_inr"].round(2)

    combined = combined[UNIFIED_COLUMNS]
    combined = combined.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    return combined


def validate(df: pd.DataFrame) -> None:
    """Basic sanity checks before handing off to FIFO matching."""
    assert df["quantity"].gt(0).all(), "Found non-positive quantity"
    assert df["price"].gt(0).all(), "Found non-positive price"
    assert df["transaction_type"].isin(["BUY", "SELL"]).all(), "Bad transaction_type"
    assert df["trade_date"].notna().all(), "Found missing trade_date"
    print(f"Validation passed: {len(df)} normalized trade rows")


def main():
    normalized = normalize_all()
    validate(normalized)
    out_path = DATA_DIR / "normalized_trades.csv"
    normalized.to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(normalized)} rows)")
    print(normalized["broker"].value_counts().to_string())


if __name__ == "__main__":
    main()
```

### 2.2 Detailed Explanation of `ingest.py`

#### Lines 1–34: Constants & Unified Column Schema
- `UNIFIED_COLUMNS`: Contains 15 fields forming the project's canonical data model.
- Notice `source_ref`: Stores the broker's original unique trade identifier (`Trade ID`, `Order Ref`, `Contract Note No`, `TransactionID`) for auditing.

#### Lines 36–44: Function `_std_side(value: str) -> str`
- **Purpose:** Cleans and normalizes buy/sell direction flags.
- **Logic:** Strips whitespace and forces uppercase. Converts `"BUY"` or `"B"` to `"BUY"`, and `"SELL"` or `"S"` to `"SELL"`. If any other string is encountered, raises a `ValueError`.

#### Lines 46–124: Broker Adapters (`load_zerodha`, `load_groww`, `load_icici_direct`, `load_interactive_brokers`)
Each adapter reads a broker-specific CSV and performs transformation into a common intermediate DataFrame:
- **Zerodha Adapter:** Parses `Trade Date` as `YYYY-MM-DD` (`%Y-%m-%d`). Sums `Brokerage` and `STT` (Securities Transaction Tax) into `charges_inr`. `fx_rate_to_inr` is fixed at `1.0`.
- **Groww Adapter:** Parses `Date` as `DD/MM/YYYY` (`%d/%m/%Y`). Maps `Ticker` to `symbol` and `Stock Name` to `company_name`. `ISIN` is set to `pd.NA`.
- **ICICI Direct Adapter:** Parses `Execution Date` as `DD-Mon-YYYY` (e.g., `14-Aug-2023`, `%d-%b-%Y`). Maps `Scrip Code` to `symbol` and `Rate` to `price`.
- **Interactive Brokers Adapter:** Deals with US equities. Parses `TradeDate` in compact ISO format `YYYYMMDD` (`%Y%m%d`). Price currency is `"USD"`. Reads `FXRateToINR`. Converts the trade commission from USD to INR dynamically: `df["Commission"] * df["FXRateToINR"]`.

#### Lines 134–146: Function `normalize_all() -> pd.DataFrame`
- Executes all 4 loaders via list comprehension and concatenates them into a single DataFrame using `pd.concat(..., ignore_index=True)`.
- Calculates derived fields:
  $$\text{price\_inr} = \text{round}(\text{price} \times \text{fx\_rate\_to\_inr}, 2)$$
  $$\text{gross\_amount\_inr} = \text{round}(\text{price\_inr} \times \text{quantity}, 2)$$
- Reorders columns to strictly match `UNIFIED_COLUMNS`.
- Sorts rows primarily by `symbol` and secondarily by `trade_date`. This ordering is mandatory so that downstream FIFO matching can process trades per symbol chronologically.

#### Lines 148–155: Function `validate(df: pd.DataFrame) -> None`
- Executes defensive sanity assertions:
  - All quantities must be strictly positive ($> 0$).
  - All prices must be strictly positive ($> 0$).
  - `transaction_type` must only contain `"BUY"` or `"SELL"`.
  - No `trade_date` may be null or NaN.

#### Lines 157–167: Entry Point `main()`
- Runs normalization, triggers validation, writes the result to `./data/normalized_trades.csv`, and prints a breakdown of trade volume per broker.

---

## 3. File: `backend/corporate_actions_adjuster.py`

### 3.1 Complete Verbatim Source Code

```python
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

import re
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"


def parse_ratio(detail: str):
    """Extract a numeric multiplier from a split/bonus ratio string like '1:2' or '2:1'."""
    match = re.search(r"(\d+)\s*:\s*(\d+)", detail)
    if not match:
        return None
    old, new = int(match.group(1)), int(match.group(2))
    # "old : new" means: for every `old` shares held, you now have `new` shares (bonus/split),
    # e.g. Split "1:2" -> 1 share becomes 2 -> multiplier 2
    # e.g. Bonus "1:1" -> 1 share becomes 2 (1 original + 1 bonus) -> multiplier 2
    return new / old if "split" in detail.lower() else (old + new) / old


def load_actions() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "corporate_actions.csv")
    df["Ex-Date"] = pd.to_datetime(df["Ex-Date"])
    return df


def apply_adjustments(trades: pd.DataFrame, actions: pd.DataFrame) -> pd.DataFrame:
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
```

### 3.2 Detailed Explanation of `corporate_actions_adjuster.py`

#### Purpose & Mathematical Foundation
If an investor bought 10 shares of Reliance at ₹2,000 on Jan 10, 2023, and a 1:1 bonus issue occurred on May 15, 2023, the investor now owns 20 shares. The total acquisition cost remains ₹20,000. Therefore, the adjusted cost per share becomes ₹1,000 ($\frac{₹20,000}{20}$). If on June 1, 2023, the investor sells 15 shares, matching against unadjusted lots would trigger an error (since only 10 original shares were recorded).

#### Lines 23–33: Function `parse_ratio(detail: str)`
- **Input:** A descriptive string such as `"Stock split 1:2"` or `"Bonus issue 1:1"`.
- **Logic:** Uses `re.search(r"(\d+)\s*:\s*(\d+)", detail)` to capture `old` and `new` integers.
  - For **Splits** (`"1:2"`): 1 share split into 2 shares $\rightarrow \text{multiplier} = \frac{\text{new}}{\text{old}} = \frac{2}{1} = 2.0$.
  - For **Bonus** (`"1:1"`): For every 1 share held, 1 bonus share is awarded $\rightarrow \text{multiplier} = \frac{\text{old} + \text{new}}{\text{old}} = \frac{1 + 1}{1} = 2.0$.
- **Return Value:** Float multiplier (e.g., `2.0`, `5.0`), or `None` if parsing fails.

#### Lines 41–70: Function `apply_adjustments`
- Copies the trades DataFrame and initializes new tracking columns: `adj_quantity`, `adj_price`, and `adjustment_note`.
- Filters corporate actions to include only `"Split"` and `"Bonus"`. Dividends and rights issues do not alter lot quantities.
- Iterates through each corporate action and constructs a Boolean mask selecting BUY transactions for that symbol that occurred **strictly before the Ex-Date**:
  ```python
  mask = (trades["symbol"] == symbol) & (trades["transaction_type"] == "BUY") & (trades["trade_date"] < ex_date)
  ```
- Adjusts the matched lots:
  $$\text{adj\_price} = \frac{\text{adj\_price}}{\text{multiplier}}$$
  $$\text{adj\_quantity} = \text{round}(\text{adj\_quantity} \times \text{multiplier})$$
- Appends an audit note (e.g., `"Bonus issue 1:1 on 2023-05-15;"`).

---

## 4. File: `backend/fifo_matcher.py`

### 4.1 Complete Verbatim Source Code

```python
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
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"


def fifo_match(trades: pd.DataFrame) -> pd.DataFrame:
    trades = trades.copy()
    trades["trade_date"] = pd.to_datetime(trades["trade_date"])
    trades = trades.sort_values(["symbol", "trade_date"])

    realized = []
    lots_by_symbol = {}

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
```

### 4.2 Detailed Explanation of `fifo_matcher.py`

#### Algorithmic Design
The FIFO matching engine uses a dictionary of queues (`lots_by_symbol = {}`), where keys are stock ticker symbols and values are `collections.deque` objects containing open BUY lots.

#### Step-by-Step Execution Sequence
1. **Sorting:** Ensures all transactions are strictly ordered by `symbol` and `trade_date`.
2. **BUY Encounter:** Creates a dictionary `{date, qty, price, broker}` and pushes it to the tail of the symbol's deque (`lots.append(...)`).
3. **SELL Encounter:**
   - Extracts `qty_to_sell`, `sell_price`, and `sell_date`.
   - Enters a `while` loop while `qty_to_sell > 0` and the queue is non-empty.
   - Inspects the oldest lot at the front of the queue: `lot = lots[0]`.
   - Computes `matched_qty = min(qty_to_sell, lot["qty"])`.
   - Calculates the holding period in calendar days:
     $$\text{holding\_days} = (\text{sell\_date} - \text{lot\_date}).\text{days}$$
   - Calculates financial metrics:
     $$\text{cost\_basis} = \text{matched\_qty} \times \text{lot\_price}$$
     $$\text{sale\_value} = \text{matched\_qty} \times \text{sell\_price}$$
     $$\text{realized\_gain} = \text{sale\_value} - \text{cost\_basis}$$
   - Deducts `matched_qty` from both `lot["qty"]` and `qty_to_sell`.
   - If `lot["qty"] <= 0`, the lot is fully exhausted; pops it from the queue using `lots.popleft()`.
4. **Unmatched Sell Handling (Short Selling / Missing History):**
   - If `qty_to_sell > 0` after all known buy lots have been exhausted, the system does not crash with an exception. Instead, it records a row with `buy_date = None`, `realized_gain_inr = None`, and `flag = "UNMATCHED_SELL_QUANTITY"`. This ensures audit compliance.

---

## 5. File: `backend/generate_datasets.py`

### 5.1 Complete Verbatim Source Code

```python
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

Run: python generate_datasets.py
Output: ./data/*.csv
"""

import random
import datetime as dt
from pathlib import Path
import pandas as pd
import numpy as np

random.seed(42)
np.random.seed(42)

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
    delta = end - start
    return start + dt.timedelta(days=random.randint(0, delta.days))

FY_START = dt.date(2022, 4, 1)
FY_END = dt.date(2025, 3, 31)


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
    datasets = {
        "zerodha_trades.csv": gen_zerodha(),
        "groww_trades.csv": gen_groww(),
        "icici_direct_trades.csv": gen_icici_direct(),
        "interactive_brokers_trades.csv": gen_interactive_brokers(),
        "corporate_actions.csv": gen_corporate_actions(),
        "foreign_dividends.csv": gen_foreign_dividends(),
    }
    for fname, df in datasets.items():
        path = OUT_DIR / fname
        df.to_csv(path, index=False)
        print(f"Generated {fname}: {len(df)} rows, columns={list(df.columns)}")


if __name__ == "__main__":
    main()
```

### 5.2 Detailed Explanation of `generate_datasets.py`

#### Purpose & Reproducibility
Simulates a real-world multi-broker trading environment without requiring live API credentials or real financial records. Uses fixed pseudo-random seeds (`random.seed(42)` and `np.random.seed(42)`), guaranteeing that every run produces the exact same dataset.

#### Key Functions
- `random_date(start, end)`: Produces uniformly distributed dates between April 1, 2022 and March 31, 2025 (covering 3 Indian financial years: FY22-23, FY23-24, FY24-25).
- `gen_zerodha(n=180)`: Generates 180 rows mimicking Zerodha's contract notes. Uses lower-case `"buy"`/`"sell"`, generates realistic Indian ISIN numbers (`INE...`), and calculates Brokerage (0.03%) and STT (0.1%).
- `gen_groww(n=150)`: Generates 150 rows mimicking Groww. Formats dates as `DD/MM/YYYY`, sets side as `"BUY"`/`"SELL"`.
- `gen_icici_direct(n=120)`: Generates 120 rows mimicking ICICI Direct with single-letter indicators `"B"`/`"S"` and dates formatted as `DD-Mon-YYYY`.
- `gen_interactive_brokers(n=90)`: Generates 90 US equity trades in USD. Includes realistic USD-INR exchange rates (₹78 to ₹87) and compact dates `YYYYMMDD`.
- `gen_corporate_actions(n=25)`: Produces 25 market events (Splits, Bonuses, Dividends, Rights).
- `gen_foreign_dividends(n=40)`: Generates 40 US dividend payouts with exact 25% US withholding tax (`wht_rate = 0.25`), referencing IRS Form 1042-S certificates.

---

## 6. File: `backend/requirements.txt`

### 6.1 Verbatim Source Code
```
fastapi>=0.110
uvicorn>=0.29
pandas>=2.0
```

### 6.2 Explanation
Specifies the minimum versions required to run the backend service:
- `fastapi>=0.110`: Ensures modern Pydantic v2 compatibility and routing performance.
- `uvicorn>=0.29`: Modern ASGI server with HTTP/1.1 and WebSocket support.
- `pandas>=2.0`: Modern Pandas engine featuring PyArrow backend enhancements and string data types.
