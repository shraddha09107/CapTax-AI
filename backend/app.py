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

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
AIML_DIR = PROJECT_DIR / "aiml"
DATA_DIR = BACKEND_DIR / "data"
FRONTEND_DIR = PROJECT_DIR / "frontend"

app = FastAPI(title="CapTax AI API", version="0.1.0")

# Allow the frontend (served separately, e.g. via a dev server) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    @app.get("/dashboard")
    def get_dashboard():
        return FileResponse(FRONTEND_DIR / "index.html")
    app.mount("/dashboard", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    if (FRONTEND_DIR / "styles").exists():
        app.mount("/styles", StaticFiles(directory=str(FRONTEND_DIR / "styles")), name="styles")

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
def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return RedirectResponse(url="/dashboard")
    return {
        "service": "CapTax AI API",
        "status": "ok",
        "dashboard_ui": "http://localhost:8001/dashboard",
        "interactive_docs": "http://localhost:8001/docs",
        "endpoints": [
            "/pipeline/run", "/data/trades", "/data/tax-summary",
            "/data/dtaa-relief", "/data/disclosure-summary",
            "/data/brokers", "/data/holdings", "/data/portfolio",
            "/data/recent-transactions",
        ],
    }


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
    dtaa_path = DATA_DIR / "dtaa_relief.csv"
    if not dtaa_path.exists():
        raise HTTPException(status_code=404, detail="dtaa_relief.csv not found — run /pipeline/run first")
    df = pd.read_csv(dtaa_path)
    div_path = DATA_DIR / "foreign_dividends.csv"
    if div_path.exists():
        div_df = pd.read_csv(div_path)
        cols_to_use = [c for c in ["TDS Certificate Ref", "Payment Date", "Gross Dividend (USD)", "Withholding Tax (USD)", "Net Dividend (USD)", "USD-INR Rate"] if c in div_df.columns]
        if "TDS Certificate Ref" in cols_to_use:
            df = pd.merge(df, div_df[cols_to_use], on="TDS Certificate Ref", how="left")
    return df.fillna("").to_dict(orient="records")


@app.get("/data/disclosure-summary")
def get_disclosure_summary():
    path = DATA_DIR / "disclosure_summary.txt"
    if not path.exists():
        raise HTTPException(status_code=404, detail="disclosure_summary.txt not found — run /pipeline/run first")
    return {"report": path.read_text()}


@app.get("/data/brokers")
def get_brokers():
    trades_path = DATA_DIR / "normalized_trades.csv"
    if not trades_path.exists():
        return []
    df = pd.read_csv(trades_path)
    brokers_meta = []
    default_brokers = {
        "Zerodha": {"country": "India", "currency": "INR", "type": "Discount Broker", "icon": "kite"},
        "Groww": {"country": "India", "currency": "INR", "type": "Direct MF & Stock", "icon": "groww"},
        "ICICI Direct": {"country": "India", "currency": "INR", "type": "Full-Service Banking", "icon": "icici"},
        "Interactive Brokers": {"country": "USA / Global", "currency": "USD", "type": "Foreign Equity & Options", "icon": "ibkr"},
    }
    grouped = df.groupby("broker")
    for broker_name, meta in default_brokers.items():
        if broker_name in grouped.groups:
            b_df = grouped.get_group(broker_name)
            brokers_meta.append({
                "broker": broker_name,
                "status": "Connected",
                "country": meta["country"],
                "currency": meta["currency"],
                "type": meta["type"],
                "icon": meta["icon"],
                "trades_count": int(len(b_df)),
                "symbols_count": int(b_df["symbol"].nunique()),
                "last_trade_date": str(b_df["trade_date"].max()) if "trade_date" in b_df.columns else "N/A",
                "total_volume_inr": float(b_df["gross_amount_inr"].sum()) if "gross_amount_inr" in b_df.columns else 0.0,
            })
        else:
            brokers_meta.append({
                "broker": broker_name,
                "status": "Configured",
                "country": meta["country"],
                "currency": meta["currency"],
                "type": meta["type"],
                "icon": meta["icon"],
                "trades_count": 0,
                "symbols_count": 0,
                "last_trade_date": "N/A",
                "total_volume_inr": 0.0,
            })
    return brokers_meta


@app.get("/data/holdings")
def get_holdings():
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
            total_buy_qty = buys["quantity"].sum()
            avg_price_inr = total_buy_cost / total_buy_qty if total_buy_qty > 0 else 0.0
            invested_inr = float(net_qty * avg_price_inr)
            currency = g["price_currency"].iloc[0] if "price_currency" in g.columns else "INR"
            company_name = g["company_name"].dropna().iloc[0] if "company_name" in g.columns and not g["company_name"].dropna().empty else symbol
            last_date = str(g["trade_date"].max())
            holdings.append({
                "broker": broker,
                "symbol": symbol,
                "company_name": company_name,
                "quantity": float(net_qty),
                "avg_price_inr": round(float(avg_price_inr), 2),
                "invested_amount_inr": round(invested_inr, 2),
                "currency": currency,
                "last_trade_date": last_date,
            })
    return sorted(holdings, key=lambda x: x["invested_amount_inr"], reverse=True)


@app.get("/data/portfolio")
def get_portfolio():
    tax_path = DATA_DIR / "tax_summary.csv"
    dtaa_path = DATA_DIR / "dtaa_relief.csv"
    
    total_tax_inr = 0.0
    total_ltcg_tax_inr = 0.0
    total_stcg_tax_inr = 0.0
    total_ltcg_gain_inr = 0.0
    total_stcg_gain_inr = 0.0
    fys = []
    
    if tax_path.exists():
        tdf = pd.read_csv(tax_path)
        total_tax_inr = float(tdf["total_tax_inr"].sum())
        total_ltcg_tax_inr = float(tdf["ltcg_tax_inr"].sum())
        total_stcg_tax_inr = float(tdf["stcg_tax_inr"].sum())
        total_ltcg_gain_inr = float(tdf["ltcg_gain_inr"].sum())
        total_stcg_gain_inr = float(tdf["stcg_gain_inr"].sum())
        fys = tdf["financial_year"].tolist()
        
    total_dtaa_relief_inr = 0.0
    total_dtaa_net_tax_inr = 0.0
    total_gross_dividend_inr = 0.0
    if dtaa_path.exists():
        ddf = pd.read_csv(dtaa_path)
        total_dtaa_relief_inr = float(ddf["dtaa_relief_inr"].sum())
        total_dtaa_net_tax_inr = float(ddf["net_indian_tax_payable_inr"].sum())
        total_gross_dividend_inr = float(ddf["gross_dividend_inr"].sum())
        
    # Holdings invested capital
    holdings = get_holdings()
    total_invested_inr = sum(h["invested_amount_inr"] for h in holdings)
    
    # Combined tax payable (capital gains tax + DTAA net payable tax)
    total_tax_payable_all_fys = round(total_tax_inr + total_dtaa_net_tax_inr, 2)
    
    # Effective tax rate across all FYs
    net_total_gains = total_ltcg_gain_inr + total_stcg_gain_inr + total_gross_dividend_inr
    effective_tax_rate = round((total_tax_payable_all_fys / net_total_gains) * 100, 2) if net_total_gains > 0 else 0.0
    
    usd_inr_rate = 83.50
    div_path = DATA_DIR / "foreign_dividends.csv"
    if div_path.exists():
        div_df = pd.read_csv(div_path)
        if "USD-INR Rate" in div_df.columns and not div_df["USD-INR Rate"].dropna().empty:
            usd_inr_rate = float(div_df["USD-INR Rate"].dropna().iloc[-1])

    return {
        "total_tax_payable_all_fys_inr": total_tax_payable_all_fys,
        "total_capital_gains_tax_inr": round(total_tax_inr, 2),
        "total_ltcg_tax_inr": round(total_ltcg_tax_inr, 2),
        "total_stcg_tax_inr": round(total_stcg_tax_inr, 2),
        "total_ltcg_gain_inr": round(total_ltcg_gain_inr, 2),
        "total_stcg_gain_inr": round(total_stcg_gain_inr, 2),
        "total_dtaa_relief_inr": round(total_dtaa_relief_inr, 2),
        "total_dtaa_net_tax_inr": round(total_dtaa_net_tax_inr, 2),
        "total_gross_dividend_inr": round(total_gross_dividend_inr, 2),
        "total_invested_inr": round(total_invested_inr, 2),
        "effective_tax_rate_pct": effective_tax_rate,
        "usd_inr_rate": round(usd_inr_rate, 2),
        "financial_years": fys,
        "holdings_count": len(holdings),
    }


@app.get("/data/recent-transactions")
def get_recent_transactions():
    txs = []
    
    # 1. Dividend payouts from dtaa_relief + foreign_dividends
    dtaa_path = DATA_DIR / "dtaa_relief.csv"
    div_path = DATA_DIR / "foreign_dividends.csv"
    if dtaa_path.exists() and div_path.exists():
        dtaa_df = pd.read_csv(dtaa_path)
        div_df = pd.read_csv(div_path)
        merged = pd.merge(dtaa_df, div_df, on="TDS Certificate Ref", how="left")
        for idx, row in merged.iterrows():
            date_raw = str(row.get("Payment Date", ""))
            try:
                date_std = pd.to_datetime(date_raw).strftime("%Y-%m-%d")
            except Exception:
                date_std = date_raw or "2024-01-01"
            sec = str(row.get("Security_x", row.get("Security", "")))
            ticker = sec.split(" - ")[0] if " - " in sec else sec[:5]
            name = sec.split(" - ")[1] if " - " in sec else sec
            gross_inr = float(row.get("gross_dividend_inr", 0.0))
            tax_withheld_inr = float(row.get("foreign_tax_withheld_inr", 0.0))
            gross_usd = float(row.get("Gross Dividend (USD)", 0.0)) if "Gross Dividend (USD)" in row else 0.0
            
            txs.append({
                "id": f"div-{row.get('TDS Certificate Ref', idx)}",
                "date": date_std,
                "ticker": ticker,
                "name": name,
                "broker": "Interactive Brokers",
                "type": "DIVIDEND",
                "category": "Foreign Dividend",
                "gross_amount_inr": round(gross_inr, 2),
                "gross_amount_usd": round(gross_usd, 2),
                "is_positive": True,
                "display_amount": f"+ ₹{gross_inr:,.2f}",
                "subline": f"US Withheld -₹{tax_withheld_inr:,.2f} • 25% DTAA",
            })
            
    # 2. Realized Trades from realized_gains.csv
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
            ticker = str(row.get("symbol", ""))
            broker = str(row.get("broker", "Broker"))
            gain_inr = float(row.get("realized_gain_inr", 0.0))
            sale_inr = float(row.get("sale_value_inr", 0.0))
            days = float(row.get("holding_period_days", 0) or 0)
            term = "LTCG" if days > 365 else "STCG"
            is_pos = gain_inr >= 0
            
            txs.append({
                "id": f"trade-{ticker}-{date_std}-{idx}",
                "date": date_std,
                "ticker": ticker,
                "name": f"{ticker} ({term})",
                "broker": broker,
                "type": "SELL_GAIN" if is_pos else "SELL_LOSS",
                "category": f"Equity Sale ({term})",
                "gross_amount_inr": round(abs(gain_inr), 2),
                "gross_amount_usd": round(abs(gain_inr) / 83.5, 2),
                "is_positive": is_pos,
                "display_amount": f"{'+ ' if is_pos else '- '}₹{abs(gain_inr):,.2f}",
                "subline": f"Sale ₹{sale_inr:,.2f} • {int(days)}d holding",
            })
            
    txs = sorted(txs, key=lambda x: x["date"], reverse=True)
    return txs
