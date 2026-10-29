# CapTax AI — UI Data Map & Backend Contract

This document maps all backend endpoints and data files to UI components across the reconstructed Datara-style frontend for **CapTax AI**.

---

## 1. Backend Routes & Request/Response Shapes

| Method | Endpoint | Source File | Response Format | Description |
|---|---|---|---|---|
| `GET` | `/` | — | JSON object | API status & endpoint directory |
| `GET` | `/dashboard` | `frontend/index.html` | HTML | Serves the single-page Datara-themed UI |
| `POST` | `/pipeline/run` | Executes 7 pipeline scripts | `{ status: "completed", steps: [...] }` | Executes ingestion, FIFO, classification, DTAA, disclosure generation |
| `GET` | `/data/tax-summary` | `backend/data/tax_summary.csv` | Array of Schedule CG rows | Schedule CG data (one row per FY) |
| `GET` | `/data/dtaa-relief` | `backend/data/dtaa_relief.csv` | Array of foreign dividend rows | Schedule FSI / DTAA relief with withholding breakdown |
| `GET` | `/data/disclosure-summary`| `backend/data/disclosure_summary.txt` | `{ report: string }` | Full monospace disclosure summary for all 3 FYs |
| `GET` | `/data/trades` | `backend/data/normalized_trades.csv`| Array of normalized trade rows | Normalized multi-broker trades |
| `GET` | `/data/realized-gains` | `backend/data/realized_gains.csv`| Array of realized gain records | FIFO matched trades with holding period & gain/loss |
| `GET` | `/data/holdings` | Derived from trades/gains | Array of active holding positions | Open positions, invested capital, current quantity |
| `GET` | `/data/brokers` | Derived from broker trades | Array of connected broker metadata | Broker accounts (Zerodha, Groww, ICICI, IBKR) |
| `GET` | `/data/recent-transactions`| Derived from trades & dividends | Array of recent events | Unified recent activity (trades + dividend credits) |
| `GET` | `/data/portfolio` | Derived from gains & tax | Summary object | Portfolio value, total tax payable, FY breakdowns |

---

## 2. Seven Pipeline Steps

1. **`generate_datasets.py`** (Owner: Anishka Jain)
   - *Inputs:* None (generates seed transactions)
   - *Outputs:* `zerodha_trades.csv`, `groww_trades.csv`, `icici_direct_trades.csv`, `interactive_brokers_trades.csv`, `corporate_actions.csv`, `foreign_dividends.csv`
2. **`ingest.py`** (Owner: Anishka Jain)
   - *Inputs:* 4 broker CSVs
   - *Outputs:* `normalized_trades.csv` (unified schema: broker, symbol, trade_date, qty, price, currency, fx_rate)
3. **`corporate_actions_adjuster.py`** (Owner: Anishka Jain)
   - *Inputs:* `normalized_trades.csv`, `corporate_actions.csv`
   - *Outputs:* `adjusted_trades.csv` (splits, bonus lot adjustments)
4. **`fifo_matcher.py`** (Owner: Anishka Jain)
   - *Inputs:* `adjusted_trades.csv`
   - *Outputs:* `realized_gains.csv` (FIFO cost-basis matching, holding periods, realized gains)
5. **`tax_classifier.py`** (Owner: Shraddha Singh)
   - *Inputs:* `realized_gains.csv`
   - *Outputs:* `classified_gains.csv`, `tax_summary.csv` (LTCG > 365 days @ 12.5%, STCG @ 20%, ₹1.25L exemption)
6. **`dtaa_relief.py`** (Owner: Shraddha Singh)
   - *Inputs:* `foreign_dividends.csv`
   - *Outputs:* `dtaa_relief.csv` (Article 25 US-India DTAA: 25% foreign tax withheld, relief, net Indian tax)
7. **`disclosure_generator.py`** (Owner: Shraddha Singh)
   - *Inputs:* `tax_summary.csv`, `dtaa_relief.csv`, `interactive_brokers_trades.csv`
   - *Outputs:* `disclosure_summary.txt` (Schedule CG, Schedule FSI, Schedule FA)

---

## 3. UI Component to Endpoint Mapping

| Page / Section | Component / Widget | Endpoint(s) | Primary Data Fields Used |
|---|---|---|---|
| **Header** | Pill Navigation | Local State | Active tab: Dashboard, Investments, Brokers, Tax, Activity |
| **Header** | Action Bar | `/pipeline/run` | "Run Pipeline" button, Settings drawer, Notification bell, User avatar |
| **Dashboard** | Hero Card ("Total Tax Payable / Portfolio") | `/data/tax-summary`, `/data/dtaa-relief`, `/data/portfolio` | Sum of `total_tax_inr` + `net_indian_tax_payable_inr`, INR/USD toggle, total portfolio value |
| **Dashboard** | Market Overview: Line Chart | `/data/tax-summary` | `ltcg_gain_inr` vs `stcg_gain_inr` across FYs (handles negative STCG for FY2024-25) |
| **Dashboard** | Market Overview: Bar Chart | `/data/tax-summary`, `/data/dtaa-relief` | Stacked bars: `ltcg_tax_inr`, `stcg_tax_inr`, `net_indian_tax_payable_inr` with active FY highlight |
| **Dashboard** | Recent Transactions Card | `/data/recent-transactions` | Date-grouped items: Ticker badge, broker label, transaction date, amount (+/-), charges/tax sub-line |
| **Dashboard** | Insights & Pipeline Log | `/data/tax-summary`, `/data/brokers` | Left: Broker quick sync cards; Right: Tax insights (e.g. STCG loss set-off, DTAA savings) |
| **Dashboard** | Tax Exposure Gauge | `/data/tax-summary` | Gauge pointer: `total_tax ÷ total_gains` for selected FY with 5-color scale & tooltip |
| **Investments** | Holdings & Portfolio Split | `/data/holdings`, `/data/trades` | Symbol, broker, qty, avg buy price, invested amount, currency split (INR vs USD) |
| **Brokers** | Broker Connection Manager | `/data/brokers` | Connected accounts (Zerodha, Groww, ICICI Direct, IBKR), last sync timestamp, upload modal |
| **Tax Page** | Schedule CG Tab | `/data/tax-summary` | `financial_year`, `ltcg_gain_inr`, `taxable_ltcg_inr`, `ltcg_tax_inr`, `stcg_gain_inr`, `stcg_tax_inr`, `total_tax_inr` |
| **Tax Page** | Schedule FSI (DTAA) Tab | `/data/dtaa-relief` | Grouped by FY & Security, expandable payout rows, visible breakdown: 25% withheld, DTAA relief, ~5% net Indian tax |
| **Tax Page** | Disclosure Report Tab | `/data/disclosure-summary` | Full monospace text output covering FY2022-23, FY2023-24, and FY2024-25 with Copy & Download |
| **Tax Page** | Assumptions & Warnings Panel | Tax rule metadata | Budget 2024 rate applicability, STCL set-off against LTCG, foreign equity distinction, Form 67 & Schedule TR pointers |
| **Activity** | Pipeline Execution History | `/pipeline/run` & Local Storage | Step-by-step progress stepper (7 steps), start/end time, execution duration, status logs |

---

## 4. Key Rules & Design Tokens

* **Title**: Strictly **"CapTax AI"** throughout all titles, headers, and reports.
* **Palette**: Dark luxury aesthetic (#0c0c0e background, #121214 cards, #F0502D orange active pill, #22c55e green positive, #ef4444 red negative, #e2e8f0 white/silver text).
* **Number Formatting**: Indian grouping standard (`en-IN`), prefixed with `₹` (or `$` when toggled to USD).
* **Zero Fake Data**: Every single metric links directly to real backend API endpoints or outputs derived faithfully from real trades.

