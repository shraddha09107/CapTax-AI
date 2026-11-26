# 03. Backend Technologies, Frameworks & Dependencies

> **Module Focus:** Complete Technological Stack Analysis  
> **Author & Mentor:** Senior Backend Developer & Technical Mentor  
> **Target Audience:** Beginner Backend Developer Preparing for Viva & Interviews

---

## 1. Verified Technology Stack Summary

An exhaustive audit of the `Backend_data` codebase reveals that the backend is built entirely in **Python** using modern ASGI web architecture, robust data manipulation libraries, and Python standard library data structures.

No database ORMs or external services are currently imported; all persistence is handled via disk-bound tabular datasets.

| Technology / Library | Version Constraint | Category | Primary Purpose in CapTax AI | Files Implementing It |
|---|---|---|---|---|
| **Python** | `>= 3.10` (tested on 3.14) | Programming Language | Core backend programming language. | All `.py` files |
| **FastAPI** | `>= 0.110` | Web Framework | High-performance ASGI REST API framework for routing, error handling, and OpenAPI generation. | `backend/app.py` |
| **Uvicorn** | `>= 0.29` | ASGI Web Server | Lightning-fast asynchronous server implementation to run FastAPI. | Invocation command for `app.py` |
| **Pandas** | `>= 2.0` | Data Analysis / ETL Engine | In-memory tabular manipulation, CSV parsing, schema transformation, and aggregations. | `ingest.py`, `corporate_actions_adjuster.py`, `fifo_matcher.py`, `generate_datasets.py`, `app.py` |
| **NumPy** | Transitive (via Pandas) | Numerical Computing | Random seed initialization and numerical vector support. | `backend/generate_datasets.py` |
| **collections.deque** | Standard Library | Data Structure | Double-ended queue used for $O(1)$ pop operations in FIFO matching. | `backend/fifo_matcher.py` |
| **pathlib.Path** | Standard Library | Filesystem Abstraction | Cross-platform, object-oriented filesystem path manipulation. | `app.py`, `ingest.py`, `corporate_actions_adjuster.py`, `fifo_matcher.py`, `generate_datasets.py` |
| **subprocess** | Standard Library | OS Process Management | Spawning independent Python subprocesses for each pipeline stage. | `backend/app.py` |
| **re** | Standard Library | Text Pattern Matching | Regex parsing of corporate action ratios (e.g., `1:2`, `1:1`). | `backend/corporate_actions_adjuster.py` |
| **datetime & random**| Standard Library | Date & Simulation Utilities | Date arithmetic, string formatting, and synthetic transaction generation. | `generate_datasets.py`, `fifo_matcher.py` |
| **CORSMiddleware** | Built into FastAPI / Starlette | HTTP Middleware | Cross-Origin Resource Sharing enablement for browser-based dashboard. | `backend/app.py` |

---

## 2. In-Depth Breakdown of Each Technology

### 2.1 Python (Core Language)
1. **What it is:** A high-level, dynamically typed, multi-paradigm programming language known for readable syntax and an unparalleled ecosystem in data science and web development.
2. **Why it is used:** CapTax AI bridges financial data wrangling (Pandas), web API serving (FastAPI), and AI/LLM integration (LangChain planned for Week 5). Python is the single language capable of executing all three domains seamlessly.
3. **Where it is used:** Every file in `Backend_data/backend/`.
4. **How it works:** Code is interpreted by the CPython runtime, compiling source code into bytecode (`.pyc`) and executing it on the virtual machine.

### 2.2 FastAPI (Web Framework)
1. **What it is:** A modern, high-performance web framework for building APIs with Python based on standard Python type hints and Starlette.
2. **Why it is used:** 
   - Speed: Comparable to NodeJS and Go.
   - Automatic interactive documentation: Automatically produces Swagger UI (`/docs`) and ReDoc (`/redoc`) without extra coding.
   - Native ASGI support: Built from the ground up for asynchronous I/O.
3. **Where it is used:** Directly in `backend/app.py`.
4. **How it works:** `app = FastAPI(title="CapTax AI API")` instantiates the application router. Decorators like `@app.get("/data/trades")` register handler functions against specific HTTP methods and URL paths. When a request matches a route, FastAPI invokes the function, parses inputs, and serializes the return value into JSON.

### 2.3 Uvicorn (ASGI Web Server)
1. **What it is:** An Asynchronous Server Gateway Interface (ASGI) web server implementation for Python, powered by `uvloop` and `httptools`.
2. **Why it is used:** Traditional WSGI servers (like Gunicorn with sync workers or Flask's development server) cannot handle asynchronous Python coroutines efficiently. Uvicorn translates raw TCP/HTTP network packets into ASGI event dictionaries that FastAPI consumes.
3. **Where it is used:** Serves as the operational host runner:
   ```bash
   uvicorn app:app --reload --port 8000
   ```
4. **How it works:** Uvicorn binds to port 8000, listens for incoming TCP socket connections, parses HTTP request headers, and forwards the ASGI scope to FastAPI's call stack.

### 2.4 Pandas (Data Manipulation & Normalization)
1. **What it is:** The open-source data analysis and manipulation library providing fast, flexible DataFrame and Series data structures.
2. **Why it is used:** Financial statements are tabular. Pandas allows CapTax AI to ingest varied CSV structures, map columns, parse multiple datetime formats (`pd.to_datetime`), perform vectorized arithmetic (converting foreign currency to INR in one line), group lots by symbol, and export clean CSVs.
3. **Where it is used:** In every single backend ETL module:
   - `ingest.py`: Normalizing 4 broker formats into 1 DataFrame.
   - `corporate_actions_adjuster.py`: Filtering and applying price/quantity multipliers.
   - `fifo_matcher.py`: Sorting trades and exporting realized gain logs.
   - `app.py`: Reading CSV files and transforming them into dictionaries via `.to_dict(orient="records")`.
4. **How it works:** Pandas constructs an in-memory 2D tabular structure (DataFrame) backed by contiguous NumPy arrays, enabling high-performance vectorized operations.

### 2.5 `collections.deque` (First-In, First-Out Queue)
1. **What it is:** A double-ended queue provided by Python’s standard library with $O(1)$ appends and pops from either end.
2. **Why it is used:** In FIFO cost-basis matching, BUY lots must be consumed in strict chronological order. A standard Python `list` has an $O(n)$ time complexity when removing the first element (`list.pop(0)`) because every remaining item in memory must be shifted left. `deque.popleft()` executes in guaranteed $O(1)$ constant time.
3. **Where it is used:** `backend/fifo_matcher.py` (lines 14, 31, 72).
4. **How it works:** `deque` is implemented internally as a doubly linked list of fixed-size memory blocks. When a SELL order consumes an entire BUY lot, `lots.popleft()` instantly discards the depleted lot head pointer without memory reorganization.

### 2.6 `pathlib.Path` (Cross-Platform Filesystem)
1. **What it is:** An object-oriented filesystem path library in the Python standard library.
2. **Why it is used:** Prevents catastrophic cross-platform path errors (e.g., forward slashes `/` on Linux/macOS vs backslashes `\` on Windows).
3. **Where it is used:** In `app.py`, `ingest.py`, `fifo_matcher.py`, etc., using idioms like `Path(__file__).resolve().parent`.
4. **How it works:** Automatically instantiates a `WindowsPath` or `PosixPath` object depending on the host operating system, overloading the `/` operator for clean, platform-agnostic path concatenation.

### 2.7 `subprocess` (Pipeline Orchestrator)
1. **What it is:** Python’s built-in module for spawning new OS processes, connecting to their input/output/error pipes, and obtaining their return codes.
2. **Why it is used:** Instead of importing scripts as in-memory Python modules, `app.py` executes each stage as an isolated command-line script (`python ingest.py`, etc.).
3. **Where it is used:** `backend/app.py` in `_run_script()`.
4. **How it works:** Spawns a child OS process using `[sys.executable, str(script_path)]`, sets the current working directory, captures output buffers (`capture_output=True`), and checks if the exit code is non-zero.

---

## 3. Technology Comparison & Academic Justification

When asked during project reviews why these choices were made, use this comparison matrix:

| Architectural Choice | What Was Used | Alternative Considered | Justification for Project Choice |
|---|---|---|---|
| **API Framework** | **FastAPI** | Flask or Django | FastAPI provides automatic OpenAPI interactive docs, native type validation, and significantly higher throughput than Flask. Django was too heavyweight for a data-centric microservice without ORM needs. |
| **Data Processing** | **Pandas** | Plain Python `csv` module or SQLite | The `csv` module requires hundreds of lines of boilerplate for datetime parsing, type conversion, and columnar aggregations. Pandas handles all normalizations in concise, vectorized operations. |
| **FIFO Algorithm** | **`collections.deque`** | SQL cursor or Python `list` | SQL queries for FIFO lot-matching require complex recursive Common Table Expressions (CTEs) or window functions. In-memory `deque` matching is intuitive, debuggable, and lightning fast. |
| **Pipeline Runner** | **`subprocess`** | In-process Python function calls | Spawning independent processes ensures complete memory isolation between pipeline steps. If one step crashes or leaks memory, it does not corrupt the web server memory. |
