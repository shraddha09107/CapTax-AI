# CapTax AI — Multi-Broker Capital Gains & Foreign Asset Tax Disclosure Engine

**Team 15** | GLA University, Mathura
Round 2 prototype — B.Tech CSE (AIML), III Year, V Semester (2026–27)

## What this is

A simplified end-to-end pipeline that takes raw trade exports from four
Indian/foreign brokers, normalizes them, matches gains via FIFO, classifies
LTCG/STCG, computes DTAA relief on foreign dividends, and generates a
disclosure summary approximating ITR Schedules CG, FA and FSI. Split into
**backend**, **AI/ML**, and **frontend** layers mapped directly to each
team member's role.

This is a **working scaffold**, not a finished product — every module is
intentionally simple so it's easy to deepen before Round 3.

## 4. Team and Roles

| Member | Role | Responsibilities | Key skills | Availability | Contact |
|---|---|---|---|---|---|
| Shraddha Singh | Team Lead & AI/Interpretation Lead | Scope, tax-rule research, LLM interpretation layer, DTAA logic | Python, LangChain, LLM APIs | 10 hrs/wk | shraddha.singh_cs.aiml24@gla.ac.in |
| Anishka Jain | Backend & Data Lead | Ingestion adapters, reconciliation engine, DB schema | Python, FastAPI, PostgreSQL | 10 hrs/wk | anishka.jain_cs.aiml24@gla.ac.in |
| Akash Singh Chauhan | Frontend & QA Lead | Dashboard UI, disclosure preview, testing, docs | React, Tailwind, Playwright | 8 hrs/wk | akash.chauhan_cs.aiml24@gla.ac.in |

## 5. Week-wise Plan and Assignments

| Week | Milestones | Shraddha (Lead/AI) | Anishka (Backend) | Akash (Frontend/QA) | Deliverables | Status |
|---|---|---|---|---|---|---|
| Week 1 | Requirements freeze | Finalize scope & tax-rule catalog | Broker data-format survey | UI wireframes | Draft SRS, rule catalog v0 | Planned |
| Week 2 | Architecture & DB | Architecture review | Schema & migrations | UI kit | ERD, API spec v1 | Planned |
| Week 3 | Ingestion module | Risk review, unblock | Broker adapters (Zerodha, Groww, Upstox) | Auth screens | Ingestion service v1 | **Done — this codebase** |
| Week 4 | Reconciliation engine | Rule-engine design | Corporate action & FX logic | Dashboard shell | Reconciliation module | **Done — this codebase** |
| Week 5 | AI interpretation layer | LLM integration for LTCG/STCG | Cost-basis (FIFO) matching | Gains reconciliation & UI | Working prototype | **Done — this codebase** |

---

## 6. How to Run Locally

### Prerequisites
- Python 3.10+
- Dependencies: `fastapi`, `uvicorn`, `pandas`, `numpy`, `pydantic`, `bcrypt`, `itsdangerous`, `pytest` (specified in `requirements.txt`)

### Start Backend & Frontend
Run from the project root:
```bash
# 1. Activate virtual environment
# On macOS / Linux:
source .venv/bin/activate
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies (if setting up fresh)
pip install -r requirements.txt

# 3. Start the FastAPI + Uvicorn server on port 8001
cd backend
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

### Access URLs
- **Public Landing Site**: [http://localhost:8001/](http://localhost:8001/)
- **Sign In Page**: [http://localhost:8001/login](http://localhost:8001/login)
- **Protected Dashboard**: [http://localhost:8001/app](http://localhost:8001/app) (or `/dashboard`)
- **Health Check Probe**: [http://localhost:8001/api/health](http://localhost:8001/api/health)
- **Interactive API Docs (Swagger)**: [http://localhost:8001/docs](http://localhost:8001/docs)

---

## 7. Run, Log In, and Change Credentials

### Default Development Credentials
| Role | Account ID | Default Password | Session TTL |
|---|---|---|---|
| Admin | `admin` | `@Admin123` | 8 Hours (Signed `httpOnly` Cookie) |

- **Rate Limiting**: 5 failed consecutive attempts trigger an automatic 60-second lockout per ID.
- **Security Guarantee**: Passwords are never stored in plaintext. The backend evaluates bcrypt salted hashes (`ADMIN_PASSWORD_HASH`), and frontend assets do not contain credentials.

### Changing Credentials for Production Deployment
Before deploying or sharing access beyond development, set environment variables:
```bash
# Generate a new bcrypt hash for your secret password
python3 -c "import bcrypt; print(bcrypt.hashpw(b'YourSecurePasswordHere', bcrypt.gensalt()).decode())"

# Export custom environment variables
export ADMIN_ID="your_custom_admin_id"
export ADMIN_PASSWORD_HASH="<generated_bcrypt_hash>"
export SESSION_SECRET="<generate_a_random_32_byte_secret>"

# Start the server
uvicorn app:app --host 0.0.0.0 --port 8001
```

### Running the Verification Suite
To verify the complete pipeline, authentication barriers, and DTAA calculation outputs:
```bash
python3 scripts/verify_pipeline.py
```

---

## 8. Frontend Architecture (Datara Theme)
Reconstructed according to the Datara reference design:
- **Design Tokens**: Near-black canvas (`#0c0c0e`), dark glass cards (`#121214`), orange-red active pill accent (`#F0502D`), 24px-28px radius, vector 3D asset graphic.
- **Top Pill Navigation**:
  - `Dashboard`: Portfolio hero card, dual Market Overview charts (spline line chart with negative zero-axis & stacked bar chart with highlighted active FY), date-grouped recent transactions, insights, and 5-segment tax exposure gauge.
  - `Investments`: Live scrip holdings, invested capital, and domestic vs. foreign currency breakdown.
  - `Brokers`: Status of connected accounts (Zerodha, Groww, ICICI Direct, Interactive Brokers).
  - `Tax & ITR`: Multi-year Schedule CG, grouped Schedule FSI (DTAA Article 25) with expandable drill-down & calculation breakdown, and complete Monospace Disclosure Report (all 3 FYs) with Copy/Download.
  - `Activity`: 7-step pipeline visual stepper and execution audit logs.
- **Zero Fake Data**: Every metric, table cell, and chart node is wired dynamically to real endpoints on `:8001`.
- For detailed route-to-component mappings, see [`docs/ui-data-map.md`](docs/ui-data-map.md).
 