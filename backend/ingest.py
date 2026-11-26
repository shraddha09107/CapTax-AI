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
from typing import Any, Callable, Dict, List, Mapping, Sequence
import re
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

UNIFIED_COLUMNS: List[str] = [
    "broker", "symbol", "company_name", "isin", "trade_date",
    "transaction_type", "quantity", "price", "price_currency",
    "fx_rate_to_inr", "price_inr", "gross_amount_inr", "charges_inr",
    "exchange", "source_ref",
    "source_file_id", "source_sheet", "source_row", "import_batch_id",
]

PROVENANCE_COLUMNS = ["source_file_id", "source_sheet", "source_row", "import_batch_id"]
REQUIRED_UPLOAD_FIELDS = ["symbol", "trade_date", "transaction_type", "quantity", "price"]


class DataValidationError(Exception):
    """Raised when trade records violate integrity or normalization constraints."""
    pass


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
        "trade_date": pd.to_datetime(df["TradeDate"].astype(str), format="%Y%m%d"),
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


LOADERS: Dict[str, Callable[[], pd.DataFrame]] = {
    "zerodha": load_zerodha,
    "groww": load_groww,
    "icici_direct": load_icici_direct,
    "interactive_brokers": load_interactive_brokers,
}


def normalize_all() -> pd.DataFrame:
    frames = [loader() for loader in LOADERS.values()]
    combined = pd.concat(frames, ignore_index=True)

    # Sample data remains the default source, with stable row provenance.
    combined["source_file_id"] = combined["broker"].str.lower().str.replace(" ", "_") + "_sample"
    combined["source_sheet"] = ""
    combined["source_row"] = combined.groupby("broker").cumcount() + 2
    combined["import_batch_id"] = "sample"

    # Derived fields
    combined["price_inr"] = (combined["price"] * combined["fx_rate_to_inr"]).round(2)
    combined["gross_amount_inr"] = (combined["price_inr"] * combined["quantity"]).round(2)
    combined["charges_inr"] = combined["charges_inr"].round(2)

    combined = combined[UNIFIED_COLUMNS]
    combined = combined.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    return combined


def auto_detect_mapping(columns: list[str]) -> tuple[str, dict[str, str]]:
    """Inspect column names and auto-detect broker + field mapping."""
    col_map = {str(c).strip().lower(): str(c) for c in columns}

    # Zerodha
    if "symbol" in col_map and "trade type" in col_map and "trade date" in col_map:
        return "Zerodha", {
            "symbol": col_map["symbol"],
            "trade_date": col_map["trade date"],
            "transaction_type": col_map["trade type"],
            "quantity": col_map.get("quantity", ""),
            "price": col_map.get("price", ""),
            "isin": col_map.get("isin", ""),
            "exchange": col_map.get("exchange", ""),
            "charges": col_map.get("brokerage", ""),
            "source_ref": col_map.get("trade id", ""),
        }

    # Groww
    if "ticker" in col_map and "txn type" in col_map and "avg price" in col_map:
        return "Groww", {
            "symbol": col_map["ticker"],
            "company_name": col_map.get("stock name", ""),
            "trade_date": col_map.get("date", ""),
            "transaction_type": col_map["txn type"],
            "quantity": col_map.get("qty", ""),
            "price": col_map["avg price"],
            "charges": col_map.get("charges", ""),
            "exchange": col_map.get("exchange segment", ""),
            "source_ref": col_map.get("order ref", ""),
        }

    # ICICI Direct
    if "scrip code" in col_map and "b/s indicator" in col_map and "execution date" in col_map:
        return "ICICI Direct", {
            "symbol": col_map["scrip code"],
            "company_name": col_map.get("company name", ""),
            "trade_date": col_map["execution date"],
            "transaction_type": col_map["b/s indicator"],
            "quantity": col_map.get("quantity traded", ""),
            "price": col_map.get("rate", ""),
            "charges": col_map.get("transaction charges", ""),
            "exchange": col_map.get("exchange", ""),
            "source_ref": col_map.get("contract note no", ""),
        }

    # Interactive Brokers
    if "tradedate" in col_map and "tradeprice" in col_map and "fxratetoinr" in col_map:
        return "Interactive Brokers", {
            "symbol": col_map.get("symbol", ""),
            "company_name": col_map.get("description", ""),
            "trade_date": col_map["tradedate"],
            "transaction_type": col_map.get("buy/sell", ""),
            "quantity": col_map.get("quantity", ""),
            "price": col_map["tradeprice"],
            "price_currency": col_map.get("currency", ""),
            "fx_rate_to_inr": col_map["fxratetoinr"],
            "charges": col_map.get("commission", ""),
            "exchange": col_map.get("exchange", ""),
            "source_ref": col_map.get("transactionid", ""),
        }

    # Generic heuristics matching common headers
    mapping = {}
    heuristics = {
        "symbol": ["symbol", "ticker", "scrip code", "scrip", "stock", "security", "asset"],
        "trade_date": ["trade date", "trade_date", "execution date", "date", "txn date", "tradedate", "time"],
        "transaction_type": ["trade type", "txn type", "b/s indicator", "buy/sell", "action", "type", "side", "b/s"],
        "quantity": ["quantity traded", "quantity", "qty", "units", "shares", "volume"],
        "price": ["avg price", "trade price", "rate", "price", "tradeprice", "unit price"],
        "company_name": ["company name", "stock name", "description", "company", "security name", "name"],
        "isin": ["isin", "isin code"],
        "exchange": ["exchange segment", "exchange", "market", "segment"],
        "charges": ["transaction charges", "brokerage", "charges", "commission", "fees"],
        "source_ref": ["contract note no", "order ref", "trade id", "order id", "transactionid", "ref", "id"],
        "price_currency": ["currency", "curr"],
        "fx_rate_to_inr": ["fx rate", "fxrate", "fxratetoinr", "fx_rate_to_inr", "conversion rate"],
    }
    for field, candidates in heuristics.items():
        for cand in candidates:
            if cand in col_map:
                mapping[field] = col_map[cand]
                break

    return "Other", mapping


def inspect_uploaded_frame(
    raw: pd.DataFrame,
    mapping: Mapping[str, str],
    *,
    broker: str = "Other",
    first_source_row: int = 2,
    excluded_rows: list[int] | None = None,
) -> dict[str, Any]:
    """Inspect and validate each row of an uploaded statement before normalization."""
    field_aliases = {"side": "transaction_type", "currency": "price_currency"}
    mapping = {field_aliases.get(k, k): v for k, v in mapping.items()}

    excluded_set = set(excluded_rows or [])
    missing = [field for field in REQUIRED_UPLOAD_FIELDS if not mapping.get(field)]
    if missing:
        return {
            "valid": False,
            "total_rows": len(raw),
            "valid_rows": 0,
            "excluded_rows": len(excluded_set),
            "errors": [{"row": -1, "row_index": -1, "source_row": -1, "field": "mapping", "issue": f"Missing required field mappings: {', '.join(missing)}", "message": f"Missing required field mappings: {', '.join(missing)}"}],
            "warnings": [],
            "duplicates": [],
            "sample_rows": [],
        }

    absent = [col for col in mapping.values() if col and col not in raw.columns]
    if absent:
        return {
            "valid": False,
            "total_rows": len(raw),
            "valid_rows": 0,
            "excluded_rows": len(excluded_set),
            "errors": [{"row": -1, "row_index": -1, "source_row": -1, "field": "mapping", "issue": f"Mapped columns missing from file: {', '.join(absent)}", "message": f"Mapped columns missing from file: {', '.join(absent)}"}],
            "warnings": [],
            "duplicates": [],
            "sample_rows": [],
        }

    errors = []
    warnings = []
    valid_count = 0
    seen_trades = set()
    duplicates = []
    sample_rows = []

    for i in range(len(raw)):
        if i in excluded_set:
            continue

        row = raw.iloc[i]
        src_row = i + first_source_row
        row_has_error = False

        # Validate Symbol
        sym_col = mapping.get("symbol")
        sym_val = str(row[sym_col]).strip() if sym_col and pd.notna(row[sym_col]) else ""
        if not sym_val or sym_val.lower() in ("nan", "none", "null", ""):
            msg = "Symbol cannot be empty"
            errors.append({"row": int(i), "row_index": int(i), "source_row": int(src_row), "field": "symbol", "value": sym_val, "issue": msg, "message": msg})
            row_has_error = True

        # Validate Trade Date
        date_col = mapping.get("trade_date")
        date_val = row[date_col] if date_col else None
        parsed_date = None
        try:
            parsed_date = pd.to_datetime(date_val, format="mixed", dayfirst=True)
            if pd.isna(parsed_date):
                raise ValueError("NaT")
        except Exception:
            try:
                parsed_date = pd.to_datetime(date_val, errors="coerce")
                if pd.isna(parsed_date):
                    raise ValueError("NaT")
            except Exception:
                msg = f"Invalid date: {date_val}"
                errors.append({"row": int(i), "row_index": int(i), "source_row": int(src_row), "field": "trade_date", "value": str(date_val), "issue": msg, "message": msg})
                row_has_error = True

        # Validate Transaction Type
        txn_col = mapping.get("transaction_type")
        txn_val = str(row[txn_col]).strip() if txn_col and pd.notna(row[txn_col]) else ""
        try:
            norm_side = _std_side(txn_val)
        except Exception:
            msg = f"Unrecognized transaction type: '{txn_val}'. Expected BUY or SELL."
            errors.append({"row": int(i), "row_index": int(i), "source_row": int(src_row), "field": "transaction_type", "value": txn_val, "issue": msg, "message": msg})
            row_has_error = True
            norm_side = txn_val

        # Validate Quantity
        qty_col = mapping.get("quantity")
        qty_val = row[qty_col] if qty_col else None
        try:
            qty_num = float(qty_val)
            if qty_num <= 0:
                msg = "Quantity must be greater than 0"
                errors.append({"row": int(i), "row_index": int(i), "source_row": int(src_row), "field": "quantity", "value": str(qty_val), "issue": msg, "message": msg})
                row_has_error = True
        except (ValueError, TypeError):
            msg = f"Non-numeric quantity: {qty_val}"
            errors.append({"row": int(i), "row_index": int(i), "source_row": int(src_row), "field": "quantity", "value": str(qty_val), "issue": msg, "message": msg})
            row_has_error = True

        # Validate Price
        price_col = mapping.get("price")
        price_val = row[price_col] if price_col else None
        try:
            price_num = float(price_val)
            if price_num <= 0:
                msg = "Price must be greater than 0"
                errors.append({"row": int(i), "row_index": int(i), "source_row": int(src_row), "field": "price", "value": str(price_val), "issue": msg, "message": msg})
                row_has_error = True
        except (ValueError, TypeError):
            msg = f"Non-numeric price: {price_val}"
            errors.append({"row": int(i), "row_index": int(i), "source_row": int(src_row), "field": "price", "value": str(price_val), "issue": msg, "message": msg})
            row_has_error = True

        # Check Duplicates
        trade_sig = (sym_val, str(parsed_date.date()) if parsed_date else str(date_val), norm_side, str(qty_val), str(price_val))
        if trade_sig in seen_trades:
            duplicates.append(int(i))
            warn_msg = f"Duplicate trade: {sym_val} {norm_side} {qty_val} @ {price_val}"
            warnings.append({"row": int(i), "row_index": int(i), "source_row": int(src_row), "field": "duplicate", "issue": warn_msg, "message": warn_msg})
        else:
            seen_trades.add(trade_sig)

        if not row_has_error:
            valid_count += 1

        if len(sample_rows) < 15:
            sample_rows.append({
                "row": int(i),
                "row_index": int(i),
                "source_row": int(src_row),
                "symbol": str(sym_val),
                "trade_date": str(parsed_date.date()) if parsed_date else str(date_val or ""),
                "side": str(norm_side),
                "transaction_type": str(norm_side),
                "quantity": float(qty_val) if pd.notna(qty_val) and str(qty_val).strip() else str(qty_val),
                "price": float(price_val) if pd.notna(price_val) and str(price_val).strip() else str(price_val),
                "status": "error" if row_has_error else ("warning" if i in duplicates else "valid"),
            })

    return {
        "valid": len(errors) == 0,
        "total_rows": int(len(raw)),
        "valid_rows": int(valid_count),
        "excluded_rows": int(len(excluded_set)),
        "errors": errors,
        "warnings": warnings,
        "duplicates": [int(d) for d in duplicates],
        "sample_rows": sample_rows,
    }


def normalize_uploaded_frame(
    raw: pd.DataFrame,
    mapping: Mapping[str, str],
    *,
    broker: str,
    source_file_id: str,
    import_batch_id: str,
    source_sheet: str = "",
    first_source_row: int = 2,
    excluded_rows: list[int] | None = None,
) -> pd.DataFrame:
    """Map an uploaded statement to the unified schema and retain provenance."""
    field_aliases = {"side": "transaction_type", "currency": "price_currency"}
    mapping = {field_aliases.get(k, k): v for k, v in mapping.items()}

    excluded_set = set(excluded_rows or [])
    if excluded_set:
        keep_indices = [i for i in range(len(raw)) if i not in excluded_set]
        raw = raw.iloc[keep_indices].reset_index(drop=True)

    missing = [field for field in REQUIRED_UPLOAD_FIELDS if not mapping.get(field)]
    if missing:
        raise ValueError(f"Missing mappings for required fields: {', '.join(missing)}")
    absent = [column for column in mapping.values() if column not in raw.columns]
    if absent:
        raise ValueError(f"Mapped source columns not found: {', '.join(absent)}")

    def values(field: str, default=""):
        source = mapping.get(field)
        return raw[source] if source else pd.Series([default] * len(raw), index=raw.index)

    quantity = pd.to_numeric(values("quantity"), errors="raise")
    price = pd.to_numeric(values("price"), errors="raise")
    fx = pd.to_numeric(values("fx_rate_to_inr", 1.0), errors="coerce").fillna(1.0)
    charges = pd.to_numeric(values("charges", 0.0), errors="coerce").fillna(0.0)
    currency = values("price_currency", "INR").fillna("INR").astype(str).str.upper()
    try:
        trade_dates = pd.to_datetime(values("trade_date"), format="mixed", dayfirst=True)
    except Exception:
        trade_dates = pd.to_datetime(values("trade_date"), errors="coerce")

    out = pd.DataFrame({
        "broker": broker,
        "symbol": values("symbol").astype(str).str.strip(),
        "company_name": values("company_name").replace("", pd.NA),
        "isin": values("isin").replace("", pd.NA),
        "trade_date": trade_dates,
        "transaction_type": values("transaction_type").apply(_std_side),
        "quantity": quantity,
        "price": price,
        "price_currency": currency,
        "fx_rate_to_inr": fx,
        "price_inr": (price * fx).round(2),
        "gross_amount_inr": (price * fx * quantity).round(2),
        "charges_inr": (charges * fx).round(2),
        "exchange": values("exchange"),
        "source_ref": values("source_ref"),
        "source_file_id": source_file_id,
        "source_sheet": source_sheet,
        "source_row": range(first_source_row, first_source_row + len(raw)),
        "import_batch_id": import_batch_id,
    })
    if out["symbol"].eq("").any() or out["symbol"].isna().any():
        raise ValueError("Symbol contains blank values")
    if quantity.le(0).any() or price.le(0).any() or fx.le(0).any():
        raise ValueError("Quantity, price, and FX rate must be positive")
    if out["trade_date"].isna().any():
        raise ValueError("Trade date contains invalid values")
    return out[UNIFIED_COLUMNS].reset_index(drop=True)


def validate(df: pd.DataFrame) -> None:
    """Robust sanity checks before handing off to FIFO matching.
    
    Replaces bare assertions with explicit DataValidationError checks
    to ensure validations remain active under optimized Python execution.
    """
    if not df["quantity"].gt(0).all():
        raise DataValidationError("Found non-positive quantity in trade records")
    if not df["price"].gt(0).all():
        raise DataValidationError("Found non-positive price in trade records")
    if not df["transaction_type"].isin(["BUY", "SELL"]).all():
        raise DataValidationError("Unrecognized transaction_type detected in trade records")
    if not df["trade_date"].notna().all():
        raise DataValidationError("Found missing trade_date in normalized trade records")
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
