# Farmacia Lumen — Executive BI & Operations Dashboard

An executive Business Intelligence and Operational Analytics web application for **Farmacia Lumen**, a 21-pharmacy Romanian retail chain spanning 8 regions over 18 months (`2025-05-01` – `2026-10-31`, 673,915 sales lines, 459,959 receipts). All monetary figures are reported in **RON, excluding VAT (`RON fără TVA`)**.

Built with an **Apothecary Executive BI** visual system (clean alabaster canvas, hairline borders, deep apothecary green accent, strict `tabular-nums`, zero decorative clutter) and paired with a read-only **Headless AI Analyst ("Ask Your Data")** panel.

---

### Challenge Deliverables
- **Application & Data Pipeline:** `/backend`, `/frontend`, `/scripts` (quickstart below)
- **AI Harness Conversation Log:** [`docs/harness_conversation.md`](docs/harness_conversation.md)
- **Reflection & Next Steps:** [Future Improvements](#future-improvements)


## Architecture

```text
problema2_database.sql.tar.gz
   │  (CLI import via scripts/setup_db.py + 11 covering indexes via scripts/create_indexes.py)
   ▼
data/farmacia.db  (SQLite, opened strictly in mode=ro + PRAGMA query_only=ON)
   │
   ├──► FastAPI Backend (backend/app/)
   │      • Shared GlobalFilters & data-hygiene predicates (returns, test promo, inactive SKU)
   │      • Bounded thread-safe LRU cache (256 entries) + async lifespan warmup
   │      • Dynamic SQL-grounded Operational Alerts engine (/api/v1/alerts)
   │      • Headless Text-to-SQL AI Analyst (/api/v1/analyst/ask)
   │           ├── Providers: gemini_api (google-genai) | gemini_cli | claude_cli
   │           └── Guardrails: SELECT/WITH-only validator, 10s progress_handler timeout, 200-row cap, 1x retry
   │
   ▼  (Vite dev proxy /api -> http://127.0.0.1:8000)
React + TypeScript + Tailwind CSS + Recharts + TanStack Query (frontend/)
   ├── Executive Overview          ├── Stores & Regions (with Drilldown Drawer)
   ├── Promotions & Margin Lab     ├── Inventory & Restock Risk (2026-10-31 Snapshot)
   ├── Customers & Loyalty         └── Operational Problems & Recommended Actions
   └── "Ask Your Data" Slide-Over Drawer (collapsible SQL + copy + tabular preview)
```

---

## Quickstart (Fastest Path)

### Prerequisites
- **Python 3.11+** and **`sqlite3`** CLI in `PATH`
- **Node.js 18+** (`npm` / `npm.cmd` on Windows)
- Place `problema2_database.sql.tar.gz` in the repository root.

### 1. Install Dependencies
```powershell
# Backend (from repository root)
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt

# Frontend (use npm.cmd on Windows PowerShell if script execution is restricted)
cd frontend
npm.cmd install
cd ..
```
*(On macOS/Linux: `source .venv/bin/activate && pip install -r backend/requirements.txt` and `npm install`.)*

### 2. Launch Everything in One Command
```powershell
python scripts/dev.py
```
`scripts/dev.py` automatically builds and indexes `data/farmacia.db` if missing, starts both servers concurrently, and shuts them down cleanly on `Ctrl+C`:
- **Dashboard UI:** `http://127.0.0.1:5173`
- **FastAPI Swagger Docs:** `http://127.0.0.1:8000/docs`

### Manual 2-Terminal Fallback
```powershell
# Terminal 1 — initialize DB & start API
.venv\Scripts\python.exe scripts/setup_db.py
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — start Vite dev server
cd frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

---

## Headless AI Analyst Setup ("Ask Your Data")

Copy `.env.example` to `.env` in the repository root and configure one provider (never commit `.env`):

```env
# Option 1 (default): Google GenAI Python SDK
ANALYST_PROVIDER=gemini_api
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-3.5-flash-lite

# Option 2: Headless Gemini CLI subprocess
# ANALYST_PROVIDER=gemini_cli
# GEMINI_CLI_BIN=gemini

# Option 3: Headless Claude CLI subprocess
# ANALYST_PROVIDER=claude_cli
# CLAUDE_CLI_BIN=claude
```

If no provider credentials are configured, the rest of the BI dashboard works normally and `/api/v1/analyst/ask` returns a clean HTTP `503` setup hint.

---

## Key Business Findings (RON fără TVA)

Every metric and alert in the dashboard is dynamically computed from `data/farmacia.db` (18-month chain totals: **47,680,504.42 RON** net revenue, **15,052,057.43 RON** gross profit at **31.57%** margin, **50,317,000.00 RON** target at **94.76%** attainment, **459,959** receipts, **2,009** return lines).

| Domain | Verified Finding | Quantified Impact (RON fără TVA) |
| --- | --- | --- |
| **Store Performance** | **Constanța Tomis Nord (#9)** suffered a permanent ~28% footfall drop starting **Nov 10, 2025** (96.3% avg attainment before vs. 69.4% after), while sibling `Constanța Centru (#10)` stayed healthy (91%–100%). | **-611,887 RON** variance (77.9% attainment; 23.2% of chain shortfall; pulls `Sud-Est` region to 87.7%) |
| **Operating Outage** | **Galați (#11)** recorded **22 consecutive zero-sales days** (`2025-08-03`–`2025-08-24`), dropping **-76.2% MoM** to 22,142 RON (31.6% attainment). | **~70,985 RON** single-month revenue dip |
| **Portfolio Transitions** | **Deva (#16)** closed `2026-06-30` with all **760 units** (177 SKUs) cleanly transferred to Timișoara (+408) & Sibiu (+352). **Cluj Mărăști (#18)** opened `2026-03-16` and ramped to 97.9% attainment with zero cannibalization of `Cluj Centru (#17)`. | **0** stranded units; clean regional absorption |
| **Promotions & Margin** | **100%** of positive-quantity below-cost sales (4,319 lines) come from promotions. **`Somn liniștit 2+1` (#9)** lost money overall (**-4,507 RON** net profit, -2.7% margin, 1,773 below-cost lines). Deepening **`Vara în siguranță`** from **-15% (2025)** to **-20% (2026)** kept revenue flat (+0.7%) while nearly halving profit. | **6,310 RON** below-cost loss on `Somn liniștit`; **-43,193 RON** YoY profit drop (-8.9 pp margin) on `Vara în siguranță` |
| **Inventory & Cadence** | As of `2026-10-31`, **209 active store-SKU pairs** are at 0 stock and **68.0%** (2,449/3,600) hold 1–5 units. Stockouts cluster in stores restocked Mon/Tue (`Oct 26–27`: Iași Palas 27, Sibiu 22, Suceava 21, Galați 21) vs. Fri (`Oct 30`: 1–3 SKUs). High-ticket blood pressure monitors (`Tensiometru Medicor`) lead risk. | **785,306 RON** open-store stock cost; **0** ledger discrepancy (`receptii - vanzari = magazin_stoc`) |
| **Targets & Pricing** | All **18/18 months** missed chain target (max store 96.9%), indicating ~4% calibration bias. **118 of 180 SKUs** were repriced in **August 2025** (+4.4% shelf price vs. +3.6% cost). | **-2,636,496 RON** total chain variance |
| **Loyalty Program** | 26,000 members drive **45.8%** of receipts but show virtually zero basket uplift (**103.99 vs. 103.38 RON AOV**; 31.58% vs. 31.56% margin), with **1,491 dormant (0-visit)** and **1,681 one-time** members. | **~155,000 RON** single-visit reactivation opportunity |
| **Data Hygiene** | **`oferte.id = 13` (`TEST - nu folosi`)** is excluded from campaign KPIs and flagged as a Low alert; **SKU #180 (`activ = 0`)** is excluded from active stockouts; **2,009 return lines (`cantitate < 0`)** are accounted separately from below-cost promo checks. | Zero silent metric distortion |

---

## Verification & Performance

Run the full automated verification suite:

```powershell
# 1. Analytical index build + read-only SQL benchmarks
.venv\Scripts\python.exe scripts/create_indexes.py

# 2. All REST endpoints: Phase 1 totals, edge cases, cold vs. warm cache parity
.venv\Scripts\python.exe scripts/verify_api.py

# 3. AI Analyst security guardrails (offline: --security-only; full live Q&A: omit flag)
.venv\Scripts\python.exe -u scripts/verify_analyst.py --security-only

# 4. Frontend TypeScript type-check & Vite production bundle
cd frontend && npm.cmd run build
```

**Observed Endpoint Latencies (`scripts/verify_api.py`):**

| Endpoint | Cold Cache | Warm Cache (LRU / Post-Warmup) |
| --- | ---: | ---: |
| `GET /api/v1/filters` | 8.1 ms | **8.3 ms** |
| `GET /api/v1/overview` (default 18M) | 1,623.4 ms | **9.3 ms** |
| `GET /api/v1/overview` (date + region + store) | 56.3 ms | **7.9 ms** |
| `GET /api/v1/stores` (default) | 1,154.7 ms | **7.0 ms** |
| `GET /api/v1/promotions` (default) | 808.1 ms | **7.0 ms** |
| `GET /api/v1/inventory` (snapshot) | 275.9 ms | **7.1 ms** |
| `GET /api/v1/customers` (default) | 1,906.8 ms | **6.2 ms** |
| `GET /api/v1/alerts` (dynamic SQL) | 304.6 ms | **4.9 ms** |

---

## Future Improvements

If this dashboard were expanded for everyday use across Farmacia Lumen, the next practical steps would be:

- **Automated Browser Testing (Selenium):** Add automated checks that open the app, switch between all 6 pages, change dates and filters, and run questions in "Ask Your Data." This ensures future updates don't accidentally break charts, filters, or numbers.
- **Usage Limits & Extra Safety Checks:** Limit how frequently the AI assistant can be queried so API costs stay predictable, and add extra automated tests for unusual inputs or edge cases to make sure the app always responds safely and clearly.
- **Regular Accuracy Checks for the AI Assistant:** Build a set of 30–50 realistic business questions (in Romanian and English) covering tricky cases like returns, closed stores, or test promotions, so we can regularly verify that the AI keeps giving accurate numbers.
- **One-Click Exports & Instant Charts:** Let managers export the restock and transfer plan directly to Excel (with Romanian characters displayed properly) or copy a quick summary of open alerts for email/chat. Also allow "Ask Your Data" to automatically show a simple chart alongside its table when comparing stores or products.
- **User Permissions & Long-Term Speed:** Add role-based access so regional or store managers only see their own locations, pre-calculate daily summaries overnight so the app stays fast even with years of data, and run all automated tests whenever changes are saved.