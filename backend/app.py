"""
CapTax AI - Backend API
Owner: Anishka Jain (Backend & Data Lead)

FastAPI app that wraps the ingestion -> FIFO -> classification -> DTAA ->
disclosure pipeline and exposes it over HTTP for the frontend dashboard.

Auth endpoints added (Step 2):
  POST /auth/login      — issue signed session cookie (httpOnly, SameSite=lax)
  POST /auth/logout     — clear session cookie
  GET  /auth/me         — validate session, return user info

Data / pipeline endpoints are now protected by require_auth().

Dev credentials (change before any real deployment):
  ADMIN_ID            env var, default: admin
  ADMIN_PASSWORD_HASH env var, default: bcrypt hash of @Admin123

Run: uvicorn app:app --reload --port 8001   (from inside backend/)
"""

import asyncio
import logging
import os
import time
import subprocess
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone

import bcrypt
from fastapi import FastAPI, HTTPException, Request, Depends, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from itsdangerous import TimestampSigner, SignatureExpired, BadSignature
from pydantic import BaseModel
import pandas as pd

# Setup structured logger
logger = logging.getLogger("captax.backend")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Paths with dynamic fallback
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent

# Check if in unified monorepo OR separate branch sibling directories
if (PROJECT_DIR / "aiml").exists():
    AIML_DIR = PROJECT_DIR / "aiml"
elif (PROJECT_DIR.parent / "AIML" / "aiml").exists():
    AIML_DIR = PROJECT_DIR.parent / "AIML" / "aiml"
else:
    AIML_DIR = PROJECT_DIR / "aiml"

DATA_DIR = BACKEND_DIR / "data"

if (PROJECT_DIR / "frontend").exists():
    FRONTEND_DIR = PROJECT_DIR / "frontend"
elif (PROJECT_DIR.parent / "Frontend_UI" / "frontend").exists():
    FRONTEND_DIR = PROJECT_DIR.parent / "Frontend_UI" / "frontend"
else:
    FRONTEND_DIR = PROJECT_DIR / "frontend"

# ---------------------------------------------------------------------------
# Auth configuration (read from environment; safe dev defaults)
# ---------------------------------------------------------------------------
ADMIN_ID = os.environ.get("ADMIN_ID", "admin")

# Default hash corresponds to password: @Admin123
# Generate a new hash: python3 -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())"
_DEFAULT_HASH = "$2b$12$gooyaYU7G9E./emawkjEw.GW5VnDq8ukmePSmfNhAWHjYQwn52Fz."
ADMIN_PASSWORD_HASH: bytes = os.environ.get(
    "ADMIN_PASSWORD_HASH", _DEFAULT_HASH
).encode()

# Session signing secret — generate a strong random secret for production
SESSION_SECRET = os.environ.get("SESSION_SECRET", "captax-dev-secret-change-me-in-prod")
SESSION_MAX_AGE = 8 * 3600   # 8 hours in seconds
COOKIE_NAME = "captax_session"

signer = TimestampSigner(SESSION_SECRET)

# ---------------------------------------------------------------------------
# Rate limiting (in-memory, per-ID)
# ---------------------------------------------------------------------------
RATE_LIMIT_MAX   = 5     # failed attempts before lockout
RATE_LIMIT_WINDOW = 60   # lockout duration in seconds

_login_attempts: dict[str, dict] = {}   # {user_id: {count, first_fail_ts, locked_until}}


def _check_rate_limit(user_id: str) -> None:
    """Raise 429 if the user_id is locked out."""
    entry = _login_attempts.get(user_id)
    if entry and entry.get("locked_until", 0) > time.time():
        remaining = int(entry["locked_until"] - time.time())
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {remaining} seconds.",
            headers={"Retry-After": str(remaining)},
        )


def _record_failure(user_id: str) -> None:
    """Increment failure counter; lock if threshold reached."""
    now = time.time()
    entry = _login_attempts.setdefault(user_id, {"count": 0, "first_fail_ts": now})
    entry["count"] += 1
    if entry["count"] >= RATE_LIMIT_MAX:
        entry["locked_until"] = now + RATE_LIMIT_WINDOW
        _login_attempts[user_id] = entry


def _clear_attempts(user_id: str) -> None:
    _login_attempts.pop(user_id, None)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def _sign_session(user_id: str) -> str:
    return signer.sign(user_id).decode()


def _unsign_session(token: str) -> str | None:
    """Return user_id if valid, None otherwise."""
    try:
        user_id = signer.unsign(token, max_age=SESSION_MAX_AGE).decode()
        return user_id
    except (SignatureExpired, BadSignature, Exception):
        return None


def require_auth(captax_session: str | None = Cookie(default=None)) -> str:
    """FastAPI dependency: validates session cookie, returns user_id."""
    if not captax_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = _unsign_session(captax_session)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return user_id


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="CapTax AI API", version="0.2.0")

# CORS — allow frontend origins with credentials
_ALLOWED_ORIGINS = [
    "http://localhost:8001",
    "http://127.0.0.1:8001",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static file serving — landing, login, dashboard, 404
# ---------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    from fastapi.staticfiles import StaticFiles

    # Explicit HTML routes
    @app.get("/")
    def get_landing():
        landing = FRONTEND_DIR / "landing.html"
        if landing.exists():
            return FileResponse(landing)
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/login")
    def get_login():
        login_file = FRONTEND_DIR / "login.html"
        if login_file.exists():
            return FileResponse(login_file)
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/app")
    @app.get("/app/{full_path:path}")
    def get_app(full_path: str = ""):
        return FileResponse(FRONTEND_DIR / "index.html")

    # Legacy /dashboard route still works
    @app.get("/dashboard")
    @app.get("/dashboard/{full_path:path}")
    def get_dashboard(full_path: str = ""):
        return FileResponse(FRONTEND_DIR / "index.html")

    # Direct static mounts for relative and absolute paths
    if (FRONTEND_DIR / "styles").exists():
        app.mount("/styles", StaticFiles(directory=str(FRONTEND_DIR / "styles")), name="styles")
    if (FRONTEND_DIR / "js").exists():
        app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend_static")

    @app.exception_handler(404)
    async def custom_404_handler(request: Request, exc: HTTPException):
        accept = request.headers.get("accept", "")
        if "text/html" in accept and (FRONTEND_DIR / "404.html").exists():
            return FileResponse(FRONTEND_DIR / "404.html", status_code=404)
        return JSONResponse(status_code=404, content={"detail": exc.detail or "Not Found"})

# ---------------------------------------------------------------------------
# Health & Status endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health_check():
    """Service health and readiness probe."""
    return {
        "status": "healthy",
        "app": "CapTax AI API",
        "version": "0.2.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": "production" if os.environ.get("ENV") == "production" else "development",
    }


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    id: str
    password: str


@app.post("/auth/login")
def auth_login(body: LoginRequest):
    user_id = body.id.strip()
    _check_rate_limit(user_id)

    # Constant-time comparison to prevent timing attacks
    id_ok = (user_id == ADMIN_ID)
    try:
        pw_ok = bcrypt.checkpw(body.password.encode(), ADMIN_PASSWORD_HASH)
    except Exception:
        pw_ok = False

    if not (id_ok and pw_ok):
        _record_failure(user_id)
        raise HTTPException(status_code=401, detail="Invalid ID or password")

    _clear_attempts(user_id)
    token = _sign_session(user_id)

    resp = JSONResponse({"authenticated": True, "id": user_id})
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True when serving over HTTPS
        path="/",
    )
    return resp


@app.post("/auth/logout")
def auth_logout():
    resp = JSONResponse({"authenticated": False})
    resp.delete_cookie(key=COOKIE_NAME, path="/")
    return resp


@app.get("/auth/me")
def auth_me(user_id: str = Depends(require_auth)):
    return {"authenticated": True, "id": user_id}


@app.get("/auth/rate-limit-status/{user_id}")
def auth_rate_limit_status(user_id: str):
    """Returns lockout status for a given ID (used by login UI for countdown)."""
    entry = _login_attempts.get(user_id)
    if entry and entry.get("locked_until", 0) > time.time():
        remaining = int(entry["locked_until"] - time.time())
        return {"locked": True, "remaining_seconds": remaining}
    return {"locked": False, "remaining_seconds": 0}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
PIPELINE = [
    (BACKEND_DIR / "generate_datasets.py",          "Anishka Jain"),
    (BACKEND_DIR / "ingest.py",                     "Anishka Jain"),
    (BACKEND_DIR / "corporate_actions_adjuster.py", "Anishka Jain"),
    (BACKEND_DIR / "fifo_matcher.py",               "Anishka Jain"),
    (AIML_DIR    / "tax_classifier.py",             "Shraddha Singh"),
    (AIML_DIR    / "dtaa_relief.py",                "Shraddha Singh"),
    (AIML_DIR    / "disclosure_generator.py",       "Shraddha Singh"),
]


def _run_script(script_path: Path) -> None:
    if not script_path.exists():
        logger.error(f"Pipeline script not found: {script_path}")
        raise HTTPException(
            status_code=500,
            detail=f"Required pipeline script '{script_path.name}' is missing on server",
        )

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=script_path.parent,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        incident_id = uuid.uuid4().hex[:8]
        logger.error(
            f"[Incident {incident_id}] Pipeline stage '{script_path.name}' failed:\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline stage '{script_path.name}' failed (Incident Ref: {incident_id}): {result.stderr.strip() or result.stdout.strip()}",
        )


def _read_csv_as_records(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{filename} not found — run /pipeline/run first",
        )
    df = pd.read_csv(path)
    return df.fillna("").to_dict(orient="records")


@app.post("/pipeline/run")
async def run_pipeline(user_id: str = Depends(require_auth)):
    """Runs every stage of the pipeline in order without blocking the event loop."""
    log = []
    for script_path, owner in PIPELINE:
        await asyncio.to_thread(_run_script, script_path)
        log.append({"step": script_path.name, "owner": owner, "status": "completed"})
    return {"status": "completed", "steps": log}


# ---------------------------------------------------------------------------
# Data endpoints — all protected
# ---------------------------------------------------------------------------
@app.get("/data/trades")
def get_trades(user_id: str = Depends(require_auth)):
    return _read_csv_as_records("normalized_trades.csv")


@app.get("/data/realized-gains")
def get_realized_gains(user_id: str = Depends(require_auth)):
    return _read_csv_as_records("realized_gains.csv")


@app.get("/data/tax-summary")
def get_tax_summary(user_id: str = Depends(require_auth)):
    return _read_csv_as_records("tax_summary.csv")


@app.get("/data/dtaa-relief")
def get_dtaa_relief(user_id: str = Depends(require_auth)):
    dtaa_path = DATA_DIR / "dtaa_relief.csv"
    if not dtaa_path.exists():
        raise HTTPException(
            status_code=404, detail="dtaa_relief.csv not found — run /pipeline/run first"
        )
    df = pd.read_csv(dtaa_path)
    div_path = DATA_DIR / "foreign_dividends.csv"
    if div_path.exists():
        div_df = pd.read_csv(div_path)
        cols_to_use = [
            c for c in [
                "TDS Certificate Ref", "Payment Date",
                "Gross Dividend (USD)", "Withholding Tax (USD)",
                "Net Dividend (USD)", "USD-INR Rate",
            ] if c in div_df.columns
        ]
        if "TDS Certificate Ref" in cols_to_use:
            df = pd.merge(df, div_df[cols_to_use], on="TDS Certificate Ref", how="left")
    return df.fillna("").to_dict(orient="records")


@app.get("/data/disclosure-summary")
def get_disclosure_summary(user_id: str = Depends(require_auth)):
    path = DATA_DIR / "disclosure_summary.txt"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="disclosure_summary.txt not found — run /pipeline/run first",
        )
    return {"report": path.read_text(encoding="utf-8")}


@app.get("/data/brokers")
def get_brokers(user_id: str = Depends(require_auth)):
    trades_path = DATA_DIR / "normalized_trades.csv"
    if not trades_path.exists():
        return []
    df = pd.read_csv(trades_path)
    brokers_meta = []
    default_brokers = {
        "Zerodha":            {"country": "India",       "currency": "INR", "type": "Discount Broker",         "icon": "kite"},
        "Groww":              {"country": "India",       "currency": "INR", "type": "Direct MF & Stock",        "icon": "groww"},
        "ICICI Direct":       {"country": "India",       "currency": "INR", "type": "Full-Service Banking",     "icon": "icici"},
        "Interactive Brokers":{"country": "USA / Global","currency": "USD", "type": "Foreign Equity & Options", "icon": "ibkr"},
    }
    grouped = df.groupby("broker")
    for broker_name, meta in default_brokers.items():
        if broker_name in grouped.groups:
            b_df = grouped.get_group(broker_name)
            brokers_meta.append({
                "broker":          broker_name,
                "status":          "Connected",
                "country":         meta["country"],
                "currency":        meta["currency"],
                "type":            meta["type"],
                "icon":            meta["icon"],
                "trades_count":    int(len(b_df)),
                "symbols_count":   int(b_df["symbol"].nunique()),
                "last_trade_date": str(b_df["trade_date"].max()) if "trade_date" in b_df.columns else "N/A",
                "total_volume_inr": float(b_df["gross_amount_inr"].sum()) if "gross_amount_inr" in b_df.columns else 0.0,
            })
        else:
            brokers_meta.append({
                "broker":          broker_name,
                "status":          "Configured",
                "country":         meta["country"],
                "currency":        meta["currency"],
                "type":            meta["type"],
                "icon":            meta["icon"],
                "trades_count":    0,
                "symbols_count":   0,
                "last_trade_date": "N/A",
                "total_volume_inr": 0.0,
            })
    return brokers_meta


@app.get("/data/holdings")
def get_holdings(user_id: str = Depends(require_auth)):
    trades_path = DATA_DIR / "adjusted_trades.csv"
    if not trades_path.exists():
        trades_path = DATA_DIR / "normalized_trades.csv"
    if not trades_path.exists():
        return []
    df = pd.read_csv(trades_path)
    df["signed_qty"] = df["quantity"] * df["transaction_type"].map({"BUY": 1, "SELL": -1})
    holdings = []
    for (broker, symbol), g in df.groupby(["broker", "symbol"]):
        net_qty = g["signed_qty"].sum()
        if net_qty > 0.0001:
            buys = g[g["transaction_type"] == "BUY"]
            total_buy_cost = (buys["quantity"] * buys["price_inr"]).sum() if "price_inr" in buys.columns else 0.0
            total_buy_qty  = buys["quantity"].sum()
            avg_price_inr  = total_buy_cost / total_buy_qty if total_buy_qty > 0 else 0.0
            invested_inr   = float(net_qty * avg_price_inr)
            currency       = g["price_currency"].iloc[0] if "price_currency" in g.columns else "INR"
            company_name   = (
                g["company_name"].dropna().iloc[0]
                if "company_name" in g.columns and not g["company_name"].dropna().empty
                else symbol
            )
            holdings.append({
                "broker":               broker,
                "symbol":               symbol,
                "company_name":         company_name,
                "quantity":             float(net_qty),
                "avg_price_inr":        round(float(avg_price_inr), 2),
                "invested_amount_inr":  round(invested_inr, 2),
                "currency":             currency,
                "last_trade_date":      str(g["trade_date"].max()),
            })
    return sorted(holdings, key=lambda x: x["invested_amount_inr"], reverse=True)


@app.get("/data/portfolio")
def get_portfolio(user_id: str = Depends(require_auth)):
    tax_path  = DATA_DIR / "tax_summary.csv"
    dtaa_path = DATA_DIR / "dtaa_relief.csv"

    total_tax_inr = total_ltcg_tax_inr = total_stcg_tax_inr = 0.0
    total_ltcg_gain_inr = total_stcg_gain_inr = 0.0
    fys = []

    if tax_path.exists():
        tdf = pd.read_csv(tax_path)
        total_tax_inr       = float(tdf["total_tax_inr"].sum())
        total_ltcg_tax_inr  = float(tdf["ltcg_tax_inr"].sum())
        total_stcg_tax_inr  = float(tdf["stcg_tax_inr"].sum())
        total_ltcg_gain_inr = float(tdf["ltcg_gain_inr"].sum())
        total_stcg_gain_inr = float(tdf["stcg_gain_inr"].sum())
        fys = tdf["financial_year"].tolist()

    total_dtaa_relief_inr = total_dtaa_net_tax_inr = total_gross_dividend_inr = 0.0
    if dtaa_path.exists():
        ddf = pd.read_csv(dtaa_path)
        total_dtaa_relief_inr   = float(ddf["dtaa_relief_inr"].sum())
        total_dtaa_net_tax_inr  = float(ddf["net_indian_tax_payable_inr"].sum())
        total_gross_dividend_inr = float(ddf["gross_dividend_inr"].sum())

    holdings = get_holdings.__wrapped__(user_id) if hasattr(get_holdings, "__wrapped__") else _get_holdings_raw()
    total_invested_inr = sum(h["invested_amount_inr"] for h in holdings)

    total_tax_payable = round(total_tax_inr + total_dtaa_net_tax_inr, 2)
    net_total_gains   = total_ltcg_gain_inr + total_stcg_gain_inr + total_gross_dividend_inr
    effective_tax_rate = round((total_tax_payable / net_total_gains) * 100, 2) if net_total_gains > 0 else 0.0

    usd_inr_rate = 83.50
    div_path = DATA_DIR / "foreign_dividends.csv"
    if div_path.exists():
        div_df = pd.read_csv(div_path)
        if "USD-INR Rate" in div_df.columns and not div_df["USD-INR Rate"].dropna().empty:
            usd_inr_rate = float(div_df["USD-INR Rate"].dropna().iloc[-1])

    return {
        "total_tax_payable_all_fys_inr": total_tax_payable,
        "total_capital_gains_tax_inr":   round(total_tax_inr, 2),
        "total_ltcg_tax_inr":            round(total_ltcg_tax_inr, 2),
        "total_stcg_tax_inr":            round(total_stcg_tax_inr, 2),
        "total_ltcg_gain_inr":           round(total_ltcg_gain_inr, 2),
        "total_stcg_gain_inr":           round(total_stcg_gain_inr, 2),
        "total_dtaa_relief_inr":         round(total_dtaa_relief_inr, 2),
        "total_dtaa_net_tax_inr":        round(total_dtaa_net_tax_inr, 2),
        "total_gross_dividend_inr":      round(total_gross_dividend_inr, 2),
        "total_invested_inr":            round(total_invested_inr, 2),
        "effective_tax_rate_pct":        effective_tax_rate,
        "usd_inr_rate":                  round(usd_inr_rate, 2),
        "financial_years":               fys,
        "holdings_count":                len(holdings),
    }


def _get_holdings_raw():
    """Internal holdings fetch without auth dependency (used by portfolio endpoint)."""
    trades_path = DATA_DIR / "adjusted_trades.csv"
    if not trades_path.exists():
        trades_path = DATA_DIR / "normalized_trades.csv"
    if not trades_path.exists():
        return []
    df = pd.read_csv(trades_path)
    df["signed_qty"] = df["quantity"] * df["transaction_type"].map({"BUY": 1, "SELL": -1})
    holdings = []
    for (broker, symbol), g in df.groupby(["broker", "symbol"]):
        net_qty = g["signed_qty"].sum()
        if net_qty > 0.0001:
            buys = g[g["transaction_type"] == "BUY"]
            total_buy_cost = (buys["quantity"] * buys["price_inr"]).sum() if "price_inr" in buys.columns else 0.0
            total_buy_qty  = buys["quantity"].sum()
            avg_price_inr  = total_buy_cost / total_buy_qty if total_buy_qty > 0 else 0.0
            invested_inr   = float(net_qty * avg_price_inr)
            company_name   = (
                g["company_name"].dropna().iloc[0]
                if "company_name" in g.columns and not g["company_name"].dropna().empty
                else symbol
            )
            holdings.append({
                "broker": broker, "symbol": symbol, "company_name": company_name,
                "quantity": float(net_qty), "avg_price_inr": round(float(avg_price_inr), 2),
                "invested_amount_inr": round(invested_inr, 2),
                "currency": g["price_currency"].iloc[0] if "price_currency" in g.columns else "INR",
                "last_trade_date": str(g["trade_date"].max()),
            })
    return sorted(holdings, key=lambda x: x["invested_amount_inr"], reverse=True)


@app.get("/data/recent-transactions")
def get_recent_transactions(user_id: str = Depends(require_auth)):
    txs = []

    dtaa_path = DATA_DIR / "dtaa_relief.csv"
    div_path  = DATA_DIR / "foreign_dividends.csv"
    if dtaa_path.exists() and div_path.exists():
        dtaa_df = pd.read_csv(dtaa_path)
        div_df  = pd.read_csv(div_path)
        merged  = pd.merge(dtaa_df, div_df, on="TDS Certificate Ref", how="left")
        for idx, row in merged.iterrows():
            date_raw = str(row.get("Payment Date", ""))
            try:
                date_std = pd.to_datetime(date_raw).strftime("%Y-%m-%d")
            except Exception:
                date_std = date_raw or "2024-01-01"
            sec    = str(row.get("Security_x", row.get("Security", "")))
            ticker = sec.split(" - ")[0] if " - " in sec else sec[:5]
            name   = sec.split(" - ")[1] if " - " in sec else sec
            gross_inr       = float(row.get("gross_dividend_inr", 0.0))
            tax_withheld_inr = float(row.get("foreign_tax_withheld_inr", 0.0))
            gross_usd       = float(row.get("Gross Dividend (USD)", 0.0)) if "Gross Dividend (USD)" in row else 0.0
            txs.append({
                "id": f"div-{row.get('TDS Certificate Ref', idx)}",
                "date": date_std, "ticker": ticker, "name": name,
                "broker": "Interactive Brokers", "type": "DIVIDEND",
                "category": "Foreign Dividend",
                "gross_amount_inr": round(gross_inr, 2),
                "gross_amount_usd": round(gross_usd, 2),
                "is_positive": True,
                "display_amount": f"+ ₹{gross_inr:,.2f}",
                "subline": f"US Withheld -₹{tax_withheld_inr:,.2f} • 25% DTAA",
            })

    gains_path = DATA_DIR / "realized_gains.csv"
    if gains_path.exists():
        gdf = pd.read_csv(gains_path)
        for idx, row in gdf.iterrows():
            if pd.isna(row.get("realized_gain_inr")):
                continue
            date_raw = str(row.get("sell_date", ""))
            try:
                date_std = pd.to_datetime(date_raw).strftime("%Y-%m-%d")
            except Exception:
                date_std = date_raw
            ticker   = str(row.get("symbol", ""))
            broker   = str(row.get("broker", "Broker"))
            gain_inr = float(row.get("realized_gain_inr", 0.0))
            sale_inr = float(row.get("sale_value_inr", 0.0))
            days     = float(row.get("holding_period_days", 0) or 0)
            term     = "LTCG" if days > 365 else "STCG"
            is_pos   = gain_inr >= 0
            txs.append({
                "id": f"trade-{ticker}-{date_std}-{idx}",
                "date": date_std, "ticker": ticker,
                "name": f"{ticker} ({term})", "broker": broker,
                "type": "SELL_GAIN" if is_pos else "SELL_LOSS",
                "category": f"Equity Sale ({term})",
                "gross_amount_inr": round(abs(gain_inr), 2),
                "gross_amount_usd": round(abs(gain_inr) / 83.5, 2),
                "is_positive": is_pos,
                "display_amount": f"{'+ ' if is_pos else '- '}₹{abs(gain_inr):,.2f}",
                "subline": f"Sale ₹{sale_inr:,.2f} • {int(days)}d holding",
            })

    return sorted(txs, key=lambda x: x["date"], reverse=True)
