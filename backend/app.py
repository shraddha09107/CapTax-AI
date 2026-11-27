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
import json
import uuid
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
from pydantic import BaseModel, Field
import pandas as pd
import shutil
import re
import io
import email
from email import policy
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None

try:  # Supports both `uvicorn app:app` and `uvicorn backend.app:app`.
    from .ingest import (
        normalize_uploaded_frame,
        REQUIRED_UPLOAD_FIELDS,
        auto_detect_mapping,
        inspect_uploaded_frame,
        normalize_all,
        UNIFIED_COLUMNS,
    )
except ImportError:
    from ingest import (
        normalize_uploaded_frame,
        REQUIRED_UPLOAD_FIELDS,
        auto_detect_mapping,
        inspect_uploaded_frame,
        normalize_all,
        UNIFIED_COLUMNS,
    )

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
IMPORT_DIR = DATA_DIR / "import_batches"

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


# ---------------------------------------------------------------------------
# Batch imports
# ---------------------------------------------------------------------------
IMPORT_FIELDS = [
    "symbol", "company_name", "isin", "trade_date", "transaction_type", "side",
    "quantity", "price", "price_currency", "currency", "fx_rate_to_inr", "charges",
    "exchange", "source_ref",
]
IMPORT_BROKERS = ["Zerodha", "Groww", "ICICI Direct", "Interactive Brokers", "Other"]
MAX_IMPORT_FILE_BYTES = 20 * 1024 * 1024


class ImportMapping(BaseModel):
    broker: str = "Other"
    columns: dict[str, str] = Field(default_factory=dict)
    excluded_rows: list[int] = Field(default_factory=list)


def _batch_dir(batch_id: str) -> Path:
    # UUID validation prevents path traversal even if an ID is manually supplied.
    try:
        canonical = str(uuid.UUID(batch_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Import batch not found")
    return IMPORT_DIR / canonical


def _load_batch(batch_id: str) -> tuple[Path, dict]:
    directory = _batch_dir(batch_id)
    metadata_path = directory / "batch.json"
    if not metadata_path.is_file():
        raise HTTPException(status_code=404, detail="Import batch not found")
    return directory, json.loads(metadata_path.read_text())


def _save_batch(directory: Path, batch: dict) -> None:
    (directory / "batch.json").write_text(json.dumps(batch, indent=2))


def _parse_ocr_text_to_frame(text: str) -> pd.DataFrame:
    """Convert raw OCR text lines into a structured DataFrame."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("No readable text detected in file")

    parsed_rows = []
    delimiter = None
    for line in lines:
        if "," in line:
            delimiter = ","
            break
        elif "\t" in line:
            delimiter = "\t"
            break
        elif "|" in line:
            delimiter = "|"
            break

    for line in lines:
        if delimiter:
            parts = [p.strip() for p in line.split(delimiter) if p.strip()]
        else:
            parts = re.split(r'\s{2,}|\t', line)
            if len(parts) <= 1:
                parts = line.split()
        if len(parts) >= 3:
            parsed_rows.append(parts)

    if not parsed_rows:
        raise ValueError("Could not detect tabular rows in OCR / text output")

    header_candidate = parsed_rows[0]
    has_letters = any(re.search(r'[A-Za-z]', c) for c in header_candidate)
    if has_letters and len(parsed_rows) > 1:
        headers = [f"Col_{i}_{c}" if not c.isalnum() else c for i, c in enumerate(header_candidate)]
        clean_headers = []
        for i, h in enumerate(headers):
            h_clean = str(h).strip() or f"Column_{i+1}"
            if h_clean in clean_headers:
                h_clean = f"{h_clean}_{i+1}"
            clean_headers.append(h_clean)
        data_rows = parsed_rows[1:]
    else:
        clean_headers = [f"Column_{i+1}" for i in range(max(len(r) for r in parsed_rows))]
        data_rows = parsed_rows

    num_cols = len(clean_headers)
    padded = []
    for r in data_rows:
        if len(r) < num_cols:
            padded.append(r + [""] * (num_cols - len(r)))
        else:
            padded.append(r[:num_cols])

    df = pd.DataFrame(padded, columns=clean_headers)
    return df


def _parse_pdf_to_frame(file_path: Path) -> pd.DataFrame:
    if not pdfplumber:
        raise ValueError("PDF extraction requires pdfplumber library")

    all_rows = []
    header = None
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    clean_row = [str(cell or "").strip().replace("\n", " ") for cell in row]
                    if not any(clean_row):
                        continue
                    if header is None:
                        header = clean_row
                    else:
                        all_rows.append(clean_row)

    if header and all_rows:
        max_cols = max(len(header), max(len(r) for r in all_rows))
        clean_headers = []
        for i in range(max_cols):
            h = header[i] if i < len(header) and header[i] else f"Column_{i+1}"
            if h in clean_headers:
                h = f"{h}_{i+1}"
            clean_headers.append(h)
        padded = []
        for r in all_rows:
            if len(r) < max_cols:
                padded.append(r + [""] * (max_cols - len(r)))
            else:
                padded.append(r[:max_cols])
        return pd.DataFrame(padded, columns=clean_headers)

    # Fallback to text extraction if no structured table lines
    text_content = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_content.append(t)
    combined_text = "\n".join(text_content)
    if combined_text.strip():
        return _parse_ocr_text_to_frame(combined_text)

    raise ValueError("No table or text could be extracted from PDF statement")


def _read_import_frame(file_path: Path, sheet: str | None = None) -> tuple[pd.DataFrame, str, list[str]]:
    suffix = file_path.suffix.lower()

    if suffix == ".csv":
        for enc in ["utf-8", "latin1", "cp1252"]:
            try:
                df = pd.read_csv(file_path, encoding=enc)
                df.columns = [str(c).strip() for c in df.columns]
                return df.dropna(how="all").reset_index(drop=True), "", []
            except Exception:
                continue
        df = pd.read_csv(file_path, sep=None, engine="python")
        df.columns = [str(c).strip() for c in df.columns]
        return df.dropna(how="all").reset_index(drop=True), "", []

    elif suffix in (".xlsx", ".xlsm"):
        workbook = pd.ExcelFile(file_path, engine="openpyxl")
        sheets = workbook.sheet_names
        if not sheets:
            raise ValueError("Workbook has no worksheets")
        selected = sheet if sheet in sheets else sheets[0]
        df = pd.read_excel(file_path, sheet_name=selected, engine="openpyxl")
        df.columns = [str(c).strip() for c in df.columns]
        return df.dropna(how="all").reset_index(drop=True), selected, sheets

    elif suffix == ".xls":
        workbook = pd.ExcelFile(file_path, engine="xlrd")
        sheets = workbook.sheet_names
        if not sheets:
            raise ValueError("Workbook has no worksheets")
        selected = sheet if sheet in sheets else sheets[0]
        df = pd.read_excel(file_path, sheet_name=selected, engine="xlrd")
        df.columns = [str(c).strip() for c in df.columns]
        return df.dropna(how="all").reset_index(drop=True), selected, sheets

    elif suffix == ".txt":
        try:
            df = pd.read_csv(file_path, sep=None, engine="python", encoding="utf-8")
        except Exception:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            df = _parse_ocr_text_to_frame(text)
        df.columns = [str(c).strip() for c in df.columns]
        return df.dropna(how="all").reset_index(drop=True), "", []

    elif suffix == ".pdf":
        df = _parse_pdf_to_frame(file_path)
        df.columns = [str(c).strip() for c in df.columns]
        return df.dropna(how="all").reset_index(drop=True), "", []

    elif suffix in (".png", ".jpg", ".jpeg", ".webp"):
        if not pytesseract or not Image:
            raise ValueError("Image OCR requires Pillow and pytesseract")
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img)
        df = _parse_ocr_text_to_frame(text)
        df.columns = [str(c).strip() for c in df.columns]
        return df.dropna(how="all").reset_index(drop=True), "", []

    else:
        raise ValueError(f"Unsupported file format '{suffix}'")


@app.get("/api/import/capabilities")
def import_capabilities(user_id: str = Depends(require_auth)):
    tess_path = shutil.which("tesseract")
    ocr_ready = (pytesseract is not None and Image is not None and tess_path is not None)
    ocr_reason = None if ocr_ready else ("Tesseract binary not found on PATH" if not tess_path else "pytesseract/Pillow not installed")

    return {
        "supported_formats": [
            {"ext": ".csv", "name": "CSV Spreadsheet", "status": "available", "description": "Comma, tab, semicolon or pipe-delimited"},
            {"ext": ".xlsx", "name": "Excel Workbook", "status": "available", "description": "Modern Excel files (.xlsx)"},
            {"ext": ".xls", "name": "Excel 97-2003", "status": "available", "description": "Legacy Excel files (.xls)"},
            {"ext": ".pdf", "name": "PDF Statements", "status": "available", "description": "Table and text extraction from digital statements"},
            {"ext": ".txt", "name": "Text Statement", "status": "available", "description": "Delimited or fixed-width exports"},
            {"ext": ".png", "name": "PNG Image", "status": "available" if ocr_ready else "unavailable", "reason": ocr_reason, "description": "Photos & screenshots via OCR"},
            {"ext": ".jpg", "name": "JPG/JPEG Image", "status": "available" if ocr_ready else "unavailable", "reason": ocr_reason, "description": "Mobile camera capture & photos"},
            {"ext": ".jpeg", "name": "JPEG Image", "status": "available" if ocr_ready else "unavailable", "reason": ocr_reason, "description": "Mobile camera capture & photos"},
            {"ext": ".webp", "name": "WebP Image", "status": "available" if ocr_ready else "unavailable", "reason": ocr_reason, "description": "Modern image format"},
        ],
        "file_types": [".csv", ".xlsx", ".xls", ".pdf", ".txt", ".png", ".jpg", ".jpeg", ".webp"],
        "max_file_bytes": MAX_IMPORT_FILE_BYTES,
        "max_file_size_mb": 20,
        "brokers": IMPORT_BROKERS,
        "fields": IMPORT_FIELDS,
        "required_fields": REQUIRED_UPLOAD_FIELDS,
        "sample_data_available": True,
        "ocr_available": ocr_ready,
        "ocr_binary_path": tess_path,
        "camera_capture_supported": True,
    }


@app.get("/api/import/status")
def import_status(user_id: str = Depends(require_auth)):
    active_batch = None
    if IMPORT_DIR.exists():
        for metadata_path in sorted(IMPORT_DIR.glob("*/batch.json"), reverse=True):
            try:
                b = json.loads(metadata_path.read_text())
                if b.get("status") == "confirmed":
                    active_batch = b
                    break
            except Exception:
                continue
    return {
        "active_dataset": "imported" if active_batch else "sample",
        "active_batch": active_batch,
        "sample_data_available": True,
    }


@app.post("/api/import/reset-sample")
def reset_to_sample_data(user_id: str = Depends(require_auth)):
    """Deactivates user import batches and restores default sample data."""
    if IMPORT_DIR.exists():
        for metadata_path in IMPORT_DIR.glob("*/batch.json"):
            try:
                b = json.loads(metadata_path.read_text())
                if b.get("status") == "confirmed":
                    b["status"] = "archived"
                    metadata_path.write_text(json.dumps(b, indent=2))
            except Exception:
                continue
    # Restore normalized_trades.csv to sample data
    normalized = normalize_all()
    normalized.to_csv(DATA_DIR / "normalized_trades.csv", index=False)
    # Re-run pipeline to refresh all outputs
    for script_path, owner in PIPELINE:
        _run_script(script_path)
    return {"status": "reset", "active_dataset": "sample", "message": "Restored sample data and recomputed pipeline"}


@app.post("/api/import/batches", status_code=201)
def create_import_batch(user_id: str = Depends(require_auth)):
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    batch_id = str(uuid.uuid4())
    directory = IMPORT_DIR / batch_id
    directory.mkdir()
    batch = {
        "id": batch_id,
        "status": "created",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "files": [],
    }
    _save_batch(directory, batch)
    return batch


@app.get("/api/import/batches/{batch_id}")
def get_import_batch(batch_id: str, user_id: str = Depends(require_auth)):
    directory, batch = _load_batch(batch_id)
    return batch


async def _extract_uploaded_file(request: Request) -> tuple[str, bytes]:
    """Extract uploaded file from multipart/form-data or binary body without third-party dependencies."""
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty upload body received")

    if "multipart/form-data" in content_type:
        header_bytes = f"Content-Type: {content_type}\r\n\r\n".encode("latin1", errors="replace")
        msg = email.message_from_bytes(header_bytes + body, policy=policy.default)
        for part in msg.iter_parts():
            fn = part.get_filename()
            payload = part.get_payload(decode=True)
            if fn and payload is not None:
                return fn, payload
            cd = part.get("Content-Disposition", "")
            if 'name="file"' in cd or 'filename=' in cd:
                match = re.search(r'filename="?([^";\r\n]+)"?', cd)
                filename = match.group(1) if match else "statement.csv"
                if payload is not None:
                    return filename, payload
        raise HTTPException(status_code=400, detail="No statement file found in multipart upload")
    else:
        filename = (
            request.headers.get("x-filename")
            or request.query_params.get("filename")
            or "statement.csv"
        )
        return filename, body


@app.post("/api/import/batches/{batch_id}/files", status_code=201)
async def upload_import_file(
    batch_id: str,
    request: Request,
    user_id: str = Depends(require_auth),
):
    directory, batch = _load_batch(batch_id)
    raw_filename, content = await _extract_uploaded_file(request)
    filename = Path(raw_filename).name
    suffix = Path(filename).suffix.lower()
    allowed_suffixes = {".csv", ".xlsx", ".xls", ".pdf", ".txt", ".png", ".jpg", ".jpeg", ".webp"}
    if suffix not in allowed_suffixes:
        raise HTTPException(
            status_code=415,
            detail=f"Format '{suffix}' not supported. Allowed formats: {', '.join(sorted(allowed_suffixes))}",
        )
    if len(content) > MAX_IMPORT_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 20 MB limit")
    file_id = str(uuid.uuid4())
    stored_name = file_id + suffix
    target = directory / stored_name
    target.write_bytes(content)

    try:
        frame, sheet, sheets = _read_import_frame(target)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not read statement: {exc}")

    if frame.empty:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Statement contains no data rows")

    columns = [str(c) for c in frame.columns]
    auto_broker, auto_map = auto_detect_mapping(columns)

    descriptor = {
        "id": file_id,
        "filename": filename,
        "stored_name": stored_name,
        "row_count": len(frame),
        "columns": columns,
        "sheet": sheet,
        "sheets": sheets,
        "broker": auto_broker,
        "mapping": auto_map,
        "excluded_rows": [],
        "status": "mapped" if all(f in auto_map for f in REQUIRED_UPLOAD_FIELDS) else "uploaded",
    }
    batch["files"].append(descriptor)
    batch["status"] = "uploading"
    _save_batch(directory, batch)
    return descriptor


def _get_batch_file(batch: dict, file_id: str) -> dict:
    match = next((item for item in batch["files"] if item["id"] == file_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="File not found in this batch")
    return match


@app.get("/api/import/batches/{batch_id}/files/{file_id}/preview")
def preview_import_file(batch_id: str, file_id: str, sheet: str | None = None, user_id: str = Depends(require_auth)):
    directory, batch = _load_batch(batch_id)
    item = _get_batch_file(batch, file_id)
    selected_sheet = sheet or item.get("sheet")
    if sheet and sheet not in item.get("sheets", []):
        raise HTTPException(status_code=422, detail="Requested worksheet is not present in this file")
    frame, selected_sheet, sheets = _read_import_frame(directory / item["stored_name"], selected_sheet)
    item["sheet"] = selected_sheet
    item["columns"] = [str(c) for c in frame.columns]
    item["row_count"] = len(frame)
    _save_batch(directory, batch)
    return {
        "file_id": file_id,
        "filename": item["filename"],
        "sheet": selected_sheet,
        "sheets": item.get("sheets", []),
        "columns": item["columns"],
        "row_count": len(frame),
        "broker": item.get("broker", "Other"),
        "mapping": item.get("mapping", {}),
        "excluded_rows": item.get("excluded_rows", []),
        "rows": frame.head(20).fillna("").to_dict(orient="records"),
    }


@app.put("/api/import/batches/{batch_id}/files/{file_id}/mapping")
def map_import_file(batch_id: str, file_id: str, body: ImportMapping, user_id: str = Depends(require_auth)):
    directory, batch = _load_batch(batch_id)
    item = _get_batch_file(batch, file_id)
    bad_fields = set(body.columns) - set(IMPORT_FIELDS)
    if bad_fields:
        raise HTTPException(status_code=422, detail=f"Unknown target fields: {', '.join(sorted(bad_fields))}")
    bad_columns = set(body.columns.values()) - set(item["columns"])
    if bad_columns:
        raise HTTPException(status_code=422, detail=f"Unknown source columns: {', '.join(sorted(bad_columns))}")

    # Normalize aliases: side -> transaction_type, currency -> price_currency
    field_aliases = {"side": "transaction_type", "currency": "price_currency"}
    canonical_mapping = {}
    for k, v in body.columns.items():
        canonical_k = field_aliases.get(k, k)
        canonical_mapping[canonical_k] = v

    item["broker"] = body.broker if body.broker in IMPORT_BROKERS else "Other"
    item["mapping"] = canonical_mapping
    item["excluded_rows"] = [int(r) for r in body.excluded_rows]
    item["status"] = "mapped"
    batch["status"] = "mapping"
    _save_batch(directory, batch)
    return {
        "file_id": file_id,
        "broker": item["broker"],
        "mapping": item["mapping"],
        "excluded_rows": item["excluded_rows"],
        "status": item["status"],
    }


def _validate_batch_frames(directory: Path, batch: dict) -> tuple[list[pd.DataFrame], list[dict], list[dict]]:
    frames = []
    errors = []
    reports = []
    for item in batch["files"]:
        try:
            raw, sheet, _ = _read_import_frame(directory / item["stored_name"], item.get("sheet"))
            inspection = inspect_uploaded_frame(
                raw,
                item.get("mapping", {}),
                broker=item.get("broker", "Other"),
                excluded_rows=item.get("excluded_rows", []),
            )
            inspection["file_id"] = item["id"]
            inspection["filename"] = item["filename"]
            reports.append(inspection)

            if not inspection["valid"]:
                item["status"] = "invalid"
                errors.append({
                    "file_id": item["id"],
                    "filename": item["filename"],
                    "error": f"{len(inspection['errors'])} validation errors found in statement rows",
                    "details": inspection["errors"][:10],
                })
            else:
                normalized = normalize_uploaded_frame(
                    raw,
                    item.get("mapping", {}),
                    broker=item.get("broker", "Other"),
                    source_file_id=item["id"],
                    import_batch_id=batch["id"],
                    source_sheet=sheet,
                    excluded_rows=item.get("excluded_rows", []),
                )
                frames.append(normalized)
                item["status"] = "valid"
        except Exception as exc:
            item["status"] = "invalid"
            errors.append({"file_id": item["id"], "filename": item["filename"], "error": str(exc), "details": []})
    return frames, errors, reports


@app.post("/api/import/batches/{batch_id}/validate")
def validate_import_batch(batch_id: str, user_id: str = Depends(require_auth)):
    directory, batch = _load_batch(batch_id)
    if not batch["files"]:
        raise HTTPException(status_code=400, detail="Upload at least one file first")
    frames, errors, reports = _validate_batch_frames(directory, batch)
    batch["status"] = "validated" if not errors else "invalid"
    _save_batch(directory, batch)
    total_valid_rows = sum(len(f) for f in frames)
    return {
        "batch_id": batch_id,
        "valid": not errors,
        "row_count": total_valid_rows,
        "files": batch["files"],
        "reports": reports,
        "errors": errors,
    }


@app.post("/api/import/batches/{batch_id}/confirm")
def confirm_import_batch(batch_id: str, user_id: str = Depends(require_auth)):
    directory, batch = _load_batch(batch_id)
    frames, errors, _ = _validate_batch_frames(directory, batch)
    if errors or not frames:
        _save_batch(directory, batch)
        raise HTTPException(status_code=422, detail={"message": "Import validation failed", "errors": errors})
    imported = pd.concat(frames, ignore_index=True)
    imported = imported.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    imported.to_csv(DATA_DIR / "normalized_trades.csv", index=False)
    batch["status"] = "confirmed"
    batch["confirmed_at"] = datetime.utcnow().isoformat() + "Z"
    _save_batch(directory, batch)
    return {
        "batch_id": batch_id,
        "status": "confirmed",
        "row_count": len(imported),
        "output": "normalized_trades.csv",
        "message": "Statement data successfully imported. Run the pipeline to compute capital gains.",
    }


@app.post("/pipeline/run")
async def run_pipeline(user_id: str = Depends(require_auth)):
    """Runs every stage of the pipeline in order without blocking the event loop."""
    log = []
    imported_batch_active = False
    if IMPORT_DIR.exists():
        for metadata_path in IMPORT_DIR.glob("*/batch.json"):
            try:
                if json.loads(metadata_path.read_text()).get("status") == "confirmed":
                    imported_batch_active = True
                    break
            except (OSError, json.JSONDecodeError):
                continue
    for script_path, owner in PIPELINE:
        # A confirmed upload has already produced normalized_trades.csv. Keep
        # the sample generator/loader from replacing it before later stages.
        if imported_batch_active and script_path.name in {"generate_datasets.py", "ingest.py"}:
            log.append({"step": script_path.name, "owner": owner, "status": "skipped", "reason": "confirmed import batch is active"})
            continue
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
