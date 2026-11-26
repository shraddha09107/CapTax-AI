# 02. Complete Backend Folder Structure & File Inventory

> **Module Focus:** `Backend_data` & Inter-Branch Structure  
> **Author & Mentor:** Senior Backend Developer & Technical Mentor  
> **Purpose:** Detailed catalog and structural breakdown of every directory and file in the backend codebase.

---

## 1. Complete Physical Directory Tree

The project workspace represents a snapshot of the multi-branch Git architecture used by the team, where each branch has been checked out or organized into peer top-level directories:

```
D:\CapTax-AI\
│
├── Backend_data/                     <--- [YOUR PRIMARY FOCUS] Backend repository branch
│   ├── backend/                      <--- Main Python backend application package
│   │   ├── app.py                    <--- Backend Entry Point & REST API Gateway (FastAPI)
│   │   ├── ingest.py                 <--- Broker data ingestion & canonical normalization
│   │   ├── corporate_actions_adjuster.py <--- Corporate actions lot reconciliation
│   │   ├── fifo_matcher.py           <--- FIFO cost-basis matching algorithm
│   │   ├── generate_datasets.py      <--- Synthetic multi-broker CSV dataset generator
│   │   ├── requirements.txt          <--- Application-level Python dependencies
│   │   └── data/                     <--- [Generated at runtime] Holds raw & processed CSVs
│   │       ├── zerodha_trades.csv
│   │       ├── groww_trades.csv
│   │       ├── icici_direct_trades.csv
│   │       ├── interactive_brokers_trades.csv
│   │       ├── corporate_actions.csv
│   │       ├── foreign_dividends.csv
│   │       ├── normalized_trades.csv
│   │       ├── adjusted_trades.csv
│   │       ├── realized_gains.csv
│   │       ├── classified_gains.csv
│   │       ├── tax_summary.csv
│   │       ├── dtaa_relief.csv
│   │       └── disclosure_summary.txt
│   ├── README.md                     <--- Backend branch specification & team roadmap
│   └── requirements.txt              <--- Root-level copy of Python dependencies
│
├── AIML/                             <--- [COLLABORATOR: Shraddha Singh] AI/Tax Compliance Branch
│   ├── aiml/
│   │   ├── tax_classifier.py         <--- Indian LTCG/STCG holding-period tax classifier
│   │   ├── dtaa_relief.py            <--- Section 90 / Article 25 DTAA foreign tax relief
│   │   └── disclosure_generator.py   <--- Human-readable text report synthesizer
│   ├── README.md
│   └── requirements.txt
│
├── Frontend_UI/                      <--- [COLLABORATOR: Akash Singh Chauhan] Dashboard Branch
│   ├── frontend/
│   │   └── index.html                <--- Single-page dashboard (HTML5 / Vanilla JS / CSS3)
│   ├── README.md
│   └── requirements.txt
│
├── main/                             <--- Main branch staging scaffold
│   ├── README.md
│   └── requirements.txt
│
└── Backend_Documentation/            <--- [THIS DOCUMENTATION] Comprehensive technical mentoring guides
    ├── 01_Backend_Overview.md
    ├── 02_Folder_Structure.md
    ├── 03_Technologies_and_Dependencies.md
    ├── 04_File_by_File_Code_Explanation.md
    ├── 05_API_Documentation.md
    ├── 06_Database_Architecture.md
    ├── 07_Backend_Workflow.md
    ├── 08_Authentication_and_Security.md
    ├── 09_Integration_Architecture.md
    ├── 10_Bugs_and_Improvements.md
    └── 11_Backend_Setup_Guide.md
```

---

## 2. Exhaustive Backend File Classification

Here is the exact categorization of every file residing within `Backend_data`:

| Relative Path | Classification | Role & Primary Responsibility | Implemented Functions / Classes |
|---|---|---|---|
| `backend/app.py` | **Backend Entry Point & API Gateway** | Exposes the FastAPI web server, routes incoming HTTP requests, orchestrates the sequential execution of backend and AI/ML pipeline scripts, and serves processed CSV data to the frontend dashboard. | `root()`, `run_pipeline()`, `get_trades()`, `get_realized_gains()`, `get_tax_summary()`, `get_dtaa_relief()`, `get_disclosure_summary()`, `_run_script()`, `_read_csv_as_records()` |
| `backend/ingest.py` | **Data Ingestion & Normalization** | Ingests 4 divergent raw broker CSV exports, standardizes column headers, unifies 5 date formats, maps buy/sell indicators, converts foreign currency (USD) to INR, computes fees, and validates rows. | `load_zerodha()`, `load_groww()`, `load_icici_direct()`, `load_interactive_brokers()`, `normalize_all()`, `validate()`, `_std_side()`, `main()` |
| `backend/corporate_actions_adjuster.py` | **Corporate Action Reconciliation** | Scans historical trades against corporate actions (Stock Splits and Bonus Issues), parses execution ratios, and retroactively updates BUY lot quantities and cost bases prior to ex-dates. | `parse_ratio()`, `load_actions()`, `apply_adjustments()`, `main()` |
| `backend/fifo_matcher.py` | **Cost-Basis Engine** | Implements the FIFO (First-In, First-Out) matching algorithm across multi-broker trades using double-ended queues (`deque`), calculating holding periods and realized gains/losses. | `fifo_match()`, `main()` |
| `backend/generate_datasets.py` | **Mock Data Generator** | Generates realistic synthetic transaction CSV files across 4 brokers, corporate actions, and foreign dividends over 3 financial years (FY 2022–2025) for testing. | `gen_zerodha()`, `gen_groww()`, `gen_icici_direct()`, `gen_interactive_brokers()`, `gen_corporate_actions()`, `gen_foreign_dividends()`, `random_date()`, `main()` |
| `backend/requirements.txt` | **Dependency Specification** | Lists minimum versioned Python package dependencies required by the backend service. | `fastapi>=0.110`, `uvicorn>=0.29`, `pandas>=2.0` |
| `requirements.txt` | **Root Dependency File** | Duplicate of `backend/requirements.txt` placed at the root of `Backend_data` for repository compliance. | `fastapi>=0.110`, `uvicorn>=0.29`, `pandas>=2.0` |
| `README.md` | **Documentation & Project Specs** | Outlines team roles, responsibilities, week-wise engineering milestones, and sprint status. | Academic project charter |
| `backend/data/` | **Flat-File Storage Directory** | Created dynamically at runtime by `generate_datasets.py` to persist intermediate and final CSV files. | 12 data files (CSV & TXT) |

---

## 3. Structural Analysis: Key Architectural Observations

### 3.1 Backend Entry Point
The designated entry point for the backend server is:
```
d:\CapTax-AI\Backend_data\backend\app.py
```
It is launched using Uvicorn:
```bash
uvicorn app:app --reload --port 8000
```
When started, it initializes the `FastAPI()` application instance, configures global Cross-Origin Resource Sharing (CORS), defines API routes, and prepares the runtime environment.

### 3.2 Configuration Files
- **Current State:** There are **no external configuration files** (such as `.env`, `config.py`, `settings.ini`, or `pyproject.toml`).
- **How Configuration is Currently Handled:** Paths and parameters are hardcoded directly into source files using `pathlib.Path(__file__)`.
- **Why This Matters:** In production, hardcoding directory structures prevents dynamic deployment across development, staging, and containerized Docker environments. Section 10 proposes a centralized `config.py` based on `pydantic-settings`.

### 3.3 Database Files
- **Current State:** There are **no SQL or NoSQL database connection scripts, migration files (Alembic), or ORM model definitions (SQLAlchemy/Tortoise)** in this version of the codebase.
- **How Data Persistence Works:** The system currently relies entirely on **flat-file CSV persistence** within the `backend/data/` directory. Each pipeline module reads from and writes to standardized CSV files on disk.
- **Historical Context:** In the team's `README.md` (Week 2 milestone), PostgreSQL schema and migrations were planned under Anishka Jain's role. For the Round 2 working scaffold, CSV flat files were selected to rapidly validate the ETL math without requiring local database setups.

### 3.4 Authentication & Authorization Files
- **Current State:** There are **no authentication or authorization files** (no `auth.py`, `jwt_handler.py`, or security middleware).
- All endpoints are public and unauthenticated. Any client capable of reaching `http://localhost:8000` can trigger pipeline execution or read financial records.

### 3.5 Helper & Utility Function Catalog
Several private utility functions are scattered across the modules:
1. `backend/app.py`:
   - `_run_script(script_path: Path) -> None`: Spawns a dedicated OS subprocess using `sys.executable` to run a pipeline stage and captures STDOUT/STDERR.
   - `_read_csv_as_records(filename: str) -> List[Dict]`: Reads a CSV from `data/`, replaces NaN values with empty strings, and serializes the DataFrame into a JSON-compatible list of dictionaries.
2. `backend/ingest.py`:
   - `_std_side(value: str) -> str`: Normalizes diverse broker strings (`"BUY"`, `"buy"`, `"B"`, `"SELL"`, `"sell"`, `"S"`) into canonical `"BUY"` or `"SELL"`.
   - `validate(df: pd.DataFrame) -> None`: Executes sanity assertions (positive quantities, positive prices, valid sides, non-null dates).
3. `backend/corporate_actions_adjuster.py`:
   - `parse_ratio(detail: str) -> float`: Uses regular expressions (`r"(\d+)\s*:\s*(\d+)"`) to compute the share multiplier for stock splits and bonus distributions.
4. `backend/generate_datasets.py`:
   - `random_date(start: dt.date, end: dt.date) -> dt.date`: Generates a uniformly distributed random calendar date between two boundaries.
