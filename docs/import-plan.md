# Import Plan & Implementation Report

## Project Overview
- **Backend**: FastAPI (`backend/app.py`) exposing auth, pipeline, import, and data endpoints.  
- **Ingestion**: `backend/ingest.py` supporting both default synthetic sample data and authenticated multi-format statement batch ingestion with audit provenance.
- **Pipeline**: Triggered via `POST /pipeline/run`, runs 7 scripts (`generate_datasets.py`, `ingest.py`, `corporate_actions_adjuster.py`, `fifo_matcher.py`, AI tax classifier, DTAA relief, disclosure generator).  
- **Frontend**: Responsive single-page application (`frontend/index.html`) featuring an interactive 5-step guided import wizard, broker management, tax reports, and portfolio analytics.

---

## Canonical Schemas & Formats
All ingestion operations converge into the canonical trade schema (`UNIFIED_COLUMNS`):
```
broker, symbol, company_name, isin, trade_date,
transaction_type, quantity, price, price_currency,
fx_rate_to_inr, price_inr, gross_amount_inr, charges_inr,
exchange, source_ref,
source_file_id, source_sheet, source_row, import_batch_id
```

### Supported Statement Formats
| Format | Handler Engine | Multi-sheet / Multi-page |
|---|---|---|
| `.csv` | Standard / flexible comma, tab, semicolon, pipe delimiters | N/A |
| `.xlsx` | `openpyxl` with dynamic worksheet selector | Supported |
| `.xls` | `xlrd` legacy Excel support | Supported |
| `.pdf` | `pdfplumber` tabular statement & text line parsing | Multi-page |
| `.txt` | Delimited / fixed-width parser | N/A |
| `.png`, `.jpg`, `.jpeg`, `.webp` | `pytesseract` + `Pillow` OCR engine | Supported |

---

## Phase Implementations & Milestones

### Phase 0: Baseline & Inspection
- Established reproducible baseline verification script `scripts/verify_pipeline.py`.
- Recorded baseline FY results:
  - FY2022-23: LTCG ₹0.00, STCG ₹23,122,250.10, Tax ₹4,624,450.02
  - FY2023-24: LTCG ₹9,394,527.37, STCG ₹20,046,153.54, Tax ₹5,167,921.63
  - FY2024-25: LTCG ₹13,285,608.96, STCG ₹-4,641,568.20, Tax ₹1,645,076.12
- Identified fake claims and hardcoded dev credentials on login and landing pages.

### Phase 1: Backend Import Service (`backend/app.py` & `backend/ingest.py`)
- Refactored `ingest.py` with:
  - `auto_detect_mapping()`: Auto-detects Zerodha, Groww, ICICI Direct, and Interactive Brokers.
  - `inspect_uploaded_frame()`: Performs row-level audit flagging missing symbols, invalid dates (`format='mixed'`), non-positive quantities/prices, and duplicates.
  - `normalize_uploaded_frame()`: Attaches provenance columns (`source_file_id`, `source_sheet`, `source_row`, `import_batch_id`) and handles row exclusions.
- Implemented authenticated REST endpoints:
  - `GET /api/import/capabilities`
  - `GET /api/import/status`
  - `POST /api/import/batches`
  - `POST /api/import/batches/{id}/files` (handles direct binary and multipart uploads)
  - `GET /api/import/batches/{id}/files/{fid}/preview`
  - `PUT /api/import/batches/{id}/files/{fid}/mapping`
  - `POST /api/import/batches/{id}/validate`
  - `POST /api/import/batches/{id}/confirm`
  - `POST /api/import/reset-sample`
- Zero-dependency multipart & binary streaming implemented without requiring external network downloads.

### Phase 2: Frontend Guided Upload Flow (`frontend/index.html`)
- Built complete 5-step guided wizard:
  1. **Upload & Capture**: Drag-and-drop dropzone, normal file picker, camera photo capture option (`capture="environment"`), and format capability pills.
  2. **Preview & Sheet Selection**: Worksheet dropdown for multi-sheet Excel files, broker selector, and live 20-row statement preview table.
  3. **Column Mapping**: Visual card mapping grid for required fields (`symbol`, `trade_date`, `side`, `quantity`, `price`) and optional fields, with re-detect action.
  4. **Row Problem Inspector**: Validation summary badges, problem row table with individual "Exclude Row" buttons and "Exclude All Problem Rows" bulk action.
  5. **Confirm & Pipeline Execution**: Batch review, animated 7-stage execution log, and direct links to Schedule CG/FSI results.
- Added active dataset banner in Brokers view with status badges ("Sample Data" vs "Imported Statements Active") and "Reset to Sample Data" button.

### Phase 3: Honest Product Surface (`frontend/landing.html` & `frontend/login.html`)
- Cleaned development credentials (`admin` / `@Admin123`) from `frontend/login.html` and added administrator guidance for configuring `ADMIN_ID` and `ADMIN_PASSWORD_HASH`.
- Updated landing page features, trust bar, and FAQs to accurately reflect supported capabilities (CSV, Excel, PDF, TXT, OCR photos, custom column mapping).

### Phase 4: Verification & Regression Gates
- `scripts/verify_pipeline.py`: 100% PASSING (9/9 regression checks).
- `scripts/verify_import_api.py`: 100% PASSING (10/10 API checks).
- `scripts/verify_import_e2e.py`: 100% PASSING (12/12 end-to-end steps covering multi-sheet Excel, problem row detection and exclusion, pipeline calculation, and reversible reset to sample data).
