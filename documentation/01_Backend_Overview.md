# 01. Backend Architecture Overview — CapTax AI

> **Project:** CapTax AI — Multi-Broker Capital Gains & Foreign Asset Tax Disclosure Engine  
> **Academic Context:** Round 2 Prototype — B.Tech CSE (AIML), III Year, V Semester (2026–27), GLA University, Mathura  
> **Team 15:** Shraddha Singh (Lead & AI), Anishka Jain (Backend & Data Lead), Akash Singh Chauhan (Frontend & QA Lead)  
> **Author & Mentor:** Senior Backend Developer & Technical Mentor  
> **Target Audience:** Backend Contributor (Junior/Beginner Backend Developer)

---

## 1. Executive Summary

**CapTax AI** is an automated financial compliance engine designed to solve one of the most frustrating problems faced by Indian retail investors and cross-border traders: **calculating accurate capital gains taxes and foreign asset disclosures across disparate brokerage platforms**.

Retail investors frequently trade equities and exchange-traded funds across multiple domestic brokers (e.g., Zerodha, Groww, ICICI Direct) and international investment portals (e.g., Interactive Brokers). When filing Indian Income Tax Returns (ITR-2 or ITR-3):
1. Every broker issues capital gain statements in different formats, naming conventions, date notations, and currency representations.
2. Inter-broker holding transfers and cross-broker FIFO (First-In, First-Out) cost-basis matching are completely ignored by individual broker statements.
3. Corporate actions (such as stock splits and bonus share distributions) dilute per-share cost bases and artificially inflate share counts, breaking simple transaction matching.
4. Foreign assets and dividend incomes require complex currency conversions (FX rates to INR) and compliance with Schedule FA (Foreign Assets), Schedule FSI (Foreign Source Income), and Double Taxation Avoidance Agreements (DTAA under Section 90/91 and Article 25 of the India-US Tax Treaty).

The **backend** of CapTax AI—primarily developed under the `Backend_data` module by Backend Lead Anishka Jain—serves as the **backbone** of this entire platform. It handles ingestion, currency normalization, corporate action reconciliation, FIFO lot matching, and pipeline orchestration through a FastAPI service.

---

## 2. Core Problem Statement & Real-World Domain Knowledge

To speak confidently about this backend during interviews, code reviews, and viva examinations, you must master the domain concepts underpinning the code:

### 2.1 The Multi-Broker Fragmentation Problem
Brokers export data according to their proprietary schemas:
- **Zerodha:** Uses contract-note style headers (`Trade Date`, `Price`, `Brokerage`, `STT`, `Trade ID`).
- **Groww:** Uses app-friendly names (`Date` in `DD/MM/YYYY`, `Avg Price`, `Charges`, `Order Ref`).
- **ICICI Direct:** Uses traditional banking headers (`Execution Date` in `DD-Mon-YYYY`, `Scrip Code`, `Rate`, `B/S Indicator`).
- **Interactive Brokers (IBKR):** Exports in US Dollars (USD) with American/ISO dates (`YYYYMMDD`), trade commissions in USD, and exchange rates.

### 2.2 The FIFO (First-In, First-Out) Rule (Section 45 of Income Tax Act)
Under Indian tax jurisprudence, when shares of the same company are purchased at different times and prices, any subsequent sale must match against the earliest acquired shares still in the portfolio. You cannot cherry-pick which lot you sold to manipulate tax liability.

### 2.3 Corporate Action Dilution
When a company executes a **Stock Split** (e.g., 1 share of ₹2,000 becomes 2 shares of ₹1,000) or issues **Bonus Shares** (e.g., 1 bonus share for every 1 share held), the quantity of previously acquired lots increases while the acquisition cost per share decreases proportionally. Failure to adjust buy lots prior to the ex-date causes downstream FIFO matching to compute wildly inaccurate gains or artificially trigger "unmatched sell" errors.

### 2.4 DTAA Relief & Foreign Dividend Taxation
When an Indian tax resident receives dividends from US equities (e.g., Apple, Microsoft), the US Internal Revenue Service (IRS) withholds 25% tax at source (Withholding Tax / Form 1042-S). Under the India-US DTAA (Article 10 & Article 25) and Section 90 of the Indian Income Tax Act, the taxpayer is entitled to tax relief equal to the **lower of**:
- The foreign tax withheld abroad, OR
- The Indian tax payable on that foreign income.

---

## 3. High-Level Backend Architecture

The backend operates as an automated multi-stage extract-transform-load (ETL) pipeline exposed via an HTTP REST API.

```mermaid
graph TD
    subgraph Data Sources ["1. Raw Broker & Market Exports"]
        Z["zerodha_trades.csv"]
        G["groww_trades.csv"]
        I["icici_direct_trades.csv"]
        IB["interactive_brokers_trades.csv"]
        CA["corporate_actions.csv"]
        FD["foreign_dividends.csv"]
    end

    subgraph Backend Core ["2. Backend ETL & Reconciliation Engine (Backend_data)"]
        GEN["generate_datasets.py<br/>(Synthetic Market Generator)"]
        ING["ingest.py<br/>(Multi-Broker Normalizer)"]
        ADJ["corporate_actions_adjuster.py<br/>(Split/Bonus Lot Adjuster)"]
        FIFO["fifo_matcher.py<br/>(FIFO Cost-Basis Engine)"]
        
        GEN -->|Raw CSVs| ING
        GEN -->|Actions| ADJ
        ING -->|normalized_trades.csv| ADJ
        ADJ -->|adjusted_trades.csv| FIFO
        FIFO -->|realized_gains.csv| OUT_FIFO[Realized Gains Output]
    end

    subgraph AIML Layer ["3. AI/ML & Compliance Interpretation Layer (AIML)"]
        TAX["tax_classifier.py<br/>(LTCG / STCG Classifier)"]
        DTAA["dtaa_relief.py<br/>(DTAA Foreign Tax Credit)"]
        DISC["disclosure_generator.py<br/>(ITR Schedule Synthesizer)"]
        
        OUT_FIFO --> TAX
        GEN -->|foreign_dividends.csv| DTAA
        TAX -->|tax_summary.csv| DISC
        DTAA -->|dtaa_relief.csv| DISC
        IB -->|Holdings Proxy| DISC
    end

    subgraph API & Delivery ["4. Backend API Gateway (FastAPI)"]
        APP["app.py<br/>FastAPI Application"]
        APP -->|Subprocess Orchestration| Backend Core
        APP -->|Subprocess Orchestration| AIML Layer
        APP -->|Data Endpoints /data/*| STORE[(backend/data/*.csv)]
    end

    subgraph Client ["5. Frontend Presentation (Frontend_UI)"]
        UI["index.html<br/>Vanilla JS Dashboard"]
        UI -->|POST /pipeline/run| APP
        UI -->|GET /data/tax-summary| APP
        UI -->|GET /data/dtaa-relief| APP
        UI -->|GET /data/disclosure-summary| APP
    end
```

---

## 4. Current State vs. Production Roadmap

It is vital to distinguish between what is implemented in this academic Round 2 prototype and what belongs on the future production roadmap:

| Capability | Current Prototype Implementation (Round 2) | Production Standard (Round 3 / Enterprise) |
|---|---|---|
| **Persistence** | Flat-file CSVs inside `backend/data/` | PostgreSQL with SQLAlchemy ORM and Alembic migrations |
| **Pipeline Trigger** | Synchronous OS `subprocess.run` inside FastAPI endpoint | Asynchronous Celery / Redis task queue with WebSockets |
| **Broker Ingestion** | Custom CSV adapters for 4 brokers | Plaid / Setu Account Aggregator APIs + PDF statement OCR |
| **Data Validation** | Python `assert` statements and Pandas types | Strict Pydantic v2 schemas and validation middleware |
| **Tax Regime** | Post-Budget 2024 flat rates (LTCG 12.5%, STCG 20%) | Slab-based progressive tax computation + Section 112A grandfathering |
| **Security & Auth** | Wildcard CORS (`*`), no authentication | OAuth2 with JWT, role-based access control (RBAC), TLS |
| **Cross-Module Setup**| Distinct branch folders (`Backend_data`, `AIML`, `Frontend_UI`) | Unified monorepo or Docker containerized microservices |

---

## 5. Scope of Your Contribution (Backend Lead Role)

As the backend developer, your explicit responsibilities and achievements in this codebase include:
1. **Multi-Source Data Ingestion Engine (`ingest.py`):**
   - Implemented 4 broker-specific adapters handling divergent column names, trade direction flags, and 5 distinct date formats.
   - Built automatic foreign exchange (FX) conversion into Indian National Rupees (INR) with commission scaling.
   - Designed a 15-column canonical unified trade schema.
2. **Reconciliation & Corporate Actions Engine (`corporate_actions_adjuster.py`):**
   - Engineered regex-based ratio parser for stock splits (e.g., `1:2`) and bonus issues (e.g., `1:1`).
   - Implemented retroactive lot modification modifying historical buy orders prior to ex-dates while preserving overall cost basis.
3. **FIFO Cost-Basis Engine (`fifo_matcher.py`):**
   - Developed an in-memory matching algorithm leveraging double-ended queues (`collections.deque`) grouped by equity symbol.
   - Accurately tracks partial lot consumption, exact holding periods in days, realized gains/losses, and flags unmatched sells.
4. **Mock Market Data Generator (`generate_datasets.py`):**
   - Created reproducible synthetic trade generators modeling 12 Indian blue-chips and 7 US equities across 3 fiscal years (FY 2022–25).
5. **REST API Gateway (`app.py`):**
   - Deployed FastAPI application with CORS middleware, automated swagger documentation, pipeline orchestration endpoint, and 5 data delivery endpoints.

In the following documents, every single file, function, algorithmic decision, and architectural trade-off will be broken down step by step.
