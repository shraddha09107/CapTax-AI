# 11. Backend Environment Setup, Execution & Viva Preparation Guide

> **Module Focus:** Complete Developer Runbook, Testing Procedures & Viva/Interview Mastery  
> **Author & Mentor:** Senior Backend Developer & Technical Mentor  
> **Target Audience:** Beginner Backend Developer Ready to Present the Project

---

## 1. System Prerequisites

Before starting the backend, verify that your machine meets the minimum runtime requirements:
- **Operating System:** Windows 10/11, macOS, or Ubuntu Linux 20.04+.
- **Python Runtime:** Python `3.10` or higher (verified compatible through Python `3.14`).
- **Package Manager:** `pip` (Python package installer).
- **Web Browser:** Any modern browser (Chrome, Edge, Firefox, Brave) for Swagger UI and the frontend dashboard.

---

## 2. Step-by-Step Installation Runbook

Open your terminal (PowerShell or Command Prompt on Windows, Bash on Linux/macOS) and execute the following commands:

### Step 1: Navigate to the Backend Directory
```powershell
cd D:\CapTax-AI\Backend_data\backend
```

### Step 2: Create an Isolated Python Virtual Environment
Creating a virtual environment ensures that the backend dependencies do not conflict with other system Python packages:
```powershell
# Create virtual environment named 'venv'
python -m venv venv
```

### Step 3: Activate the Virtual Environment
- **On Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
  *(If PowerShell displays an `Execution_Policy` error, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` once).*
- **On Windows (CMD):**
  ```cmd
  venv\Scripts\activate.bat
  ```
- **On Linux / macOS:**
  ```bash
  source venv/bin/activate
  ```

### Step 4: Install Required Packages
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```
This installs:
- `fastapi>=0.110`
- `uvicorn>=0.29`
- `pandas>=2.0` (which automatically installs `numpy`)

---

## 3. Running Backend Pipeline Stages from CLI

You can execute every backend module individually from the command line in its correct logical order:

```powershell
# 1. Generate synthetic market datasets (creates ./data/*.csv)
python generate_datasets.py

# 2. Ingest and normalize broker CSVs (creates ./data/normalized_trades.csv)
python ingest.py

# 3. Adjust for stock splits and bonus issues (creates ./data/adjusted_trades.csv)
python corporate_actions_adjuster.py

# 4. Run FIFO cost-basis matching (creates ./data/realized_gains.csv)
python fifo_matcher.py
```

---

## 4. Launching the Backend REST API Server

To start the FastAPI web service:

```powershell
uvicorn app:app --reload --port 8000
```

### Explanation of Flags:
- `app:app`: The first `app` refers to the Python module (`app.py`); the second `app` refers to the `FastAPI()` instance declared inside `app.py`.
- `--reload`: Enables hot-reloading. The server automatically restarts whenever you save changes to your Python files.
- `--port 8000`: Binds the web server to TCP port 8000.

Upon successful startup, Uvicorn outputs:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## 5. Verifying & Testing the API

### Method 1: Browser Verification
Open your browser and navigate to:
- `http://localhost:8000/`: Returns the root JSON service discovery payload.

### Method 2: Interactive Swagger UI Documentation
FastAPI automatically generates an interactive OpenAPI documentation dashboard at:
- `http://localhost:8000/docs`

You can test every endpoint directly from the browser:
1. Click on `POST /pipeline/run`.
2. Click **Try it out**, then **Execute**.
3. View the 200 OK execution log.
4. Next, expand `GET /data/tax-summary`, click **Try it out**, and **Execute** to see real tax calculations.

### Method 3: Testing via PowerShell / cURL
Open a separate terminal window and test using PowerShell's built-in REST client:

```powershell
# 1. Health check
Invoke-RestMethod -Uri "http://localhost:8000/" -Method GET

# 2. Trigger pipeline
Invoke-RestMethod -Uri "http://localhost:8000/pipeline/run" -Method POST

# 3. Fetch tax summary
Invoke-RestMethod -Uri "http://localhost:8000/data/tax-summary" -Method GET | Format-Table
```

---

## 6. Launching and Connecting the Frontend Dashboard

1. Keep the Uvicorn server running on port 8000.
2. In your file explorer, navigate to:
   ```
   D:\CapTax-AI\Frontend_UI\frontend\index.html
   ```
3. Double-click `index.html` to open it in your browser (or use VS Code Live Server).
4. Verify the API base URL is set to `http://localhost:8000`.
5. Click **Run Pipeline**; watch the status update and observe the Tax Summary, DTAA Relief, and Disclosure Report populate in real time!

---

## 7. Viva Examination & Technical Interview Preparation Cheat Sheet

As the backend developer, use these questions and high-impact answers to excel in your project viva or technical interview:

### Q1: "What was your specific contribution to CapTax AI?"
> **Answer:**  
> "I developed the entire backend data ingestion, reconciliation, and API serving engine in Python and FastAPI. Specifically:
> 1. I created multi-broker ingestion adapters in `ingest.py` to reconcile divergent trade exports from Zerodha, Groww, ICICI Direct, and Interactive Brokers into a canonical 15-column schema, resolving mixed date formats, transaction notations, and USD-to-INR conversions.
> 2. I engineered the corporate action adjuster in `corporate_actions_adjuster.py` to retroactively dilute buy lot prices and inflate share counts for stock splits and bonus issues.
> 3. I implemented the FIFO cost-basis matching algorithm in `fifo_matcher.py` using `collections.deque` for $O(1)$ efficiency to compute holding days and realized capital gains.
> 4. Finally, I built the FastAPI REST service in `app.py` to orchestrate pipeline stages and expose structured endpoints for the frontend."

### Q2: "Why did you use `collections.deque` instead of a standard Python list for FIFO matching?"
> **Answer:**  
> "In FIFO matching, BUY lots must be consumed in strict chronological order. If we use a standard Python `list` and call `list.pop(0)`, Python must shift every subsequent element in memory to the left, which has an $O(n)$ time complexity. For large portfolios with thousands of trades, this causes severe performance bottlenecks. By using `collections.deque`, which is implemented internally as a doubly linked list of memory blocks, `deque.popleft()` executes in guaranteed $O(1)$ constant time, making our cost-basis matching significantly more scalable."

### Q3: "How does your corporate action engine preserve the cost basis of an investment?"
> **Answer:**  
> "When a company announces a stock split (e.g., 1:2) or bonus issue (e.g., 1:1), the investor's total monetary investment does not change, but their share count doubles. In `corporate_actions_adjuster.py`, I parse the ratio using regex to calculate the multiplier. For every BUY lot dated prior to the corporate action's Ex-Date, I multiply the quantity by the multiplier and divide the per-share price by the same multiplier. Because $\text{quantity} \times \text{price} = (\text{quantity} \times M) \times (\frac{\text{price}}{M})$, the total historical cost basis is mathematically preserved while accurately reflecting the post-action share count."

### Q4: "How does the backend interact with the AI/ML module?"
> **Answer:**  
> "The backend acts as the orchestrator. In `app.py`, the `/pipeline/run` endpoint executes pipeline stages sequentially. Once my backend modules finish generating `normalized_trades.csv`, `adjusted_trades.csv`, and `realized_gains.csv`, the backend triggers Shraddha's AI/ML scripts (`tax_classifier.py`, `dtaa_relief.py`, `disclosure_generator.py`) as child subprocesses. The AI/ML scripts consume the backend's CSV data contracts and write `tax_summary.csv` and `dtaa_relief.csv`, which my FastAPI endpoints then serialize into JSON for the frontend."

### Q5: "What are the limitations of the current prototype and how would you scale it for production?"
> **Answer:**  
> "Currently, the prototype uses CSV flat files and synchronous `subprocess.run` calls for rapid academic validation. For production:
> 1. We would migrate from CSV flat files to a relational PostgreSQL database managed via SQLAlchemy ORM and Alembic migrations.
> 2. We would replace synchronous subprocesses with an asynchronous task queue like Celery with Redis, allowing long-running tax calculations to run in the background.
> 3. We would implement JWT authentication and row-level security so each user's financial records are isolated.
> 4. We would isolate FIFO queues per Demat account to strictly comply with CBDT guidelines."
