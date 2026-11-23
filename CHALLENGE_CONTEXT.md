# Project Brief: Farmacia Lumen — Executive BI & Operations Dashboard

## 1. Objective
Build a full-stack Business Intelligence (BI) and Operational Analytics web application for **Farmacia Lumen**, a fictional Romanian pharmacy chain. The dashboard must provide leadership and regional managers with a complete view of business performance: **what** is selling, **where**, **when**, **what operational problems exist**, and **what concrete actions should be taken**.

---

## 2. Dataset Specifications
* **Archive:** `problema2_database.sql.tar.gz` (SQLite SQL dump).
* **Scope:** 21 pharmacies across multiple regions.
* **Timeframe:** May 1, 2025 – October 31, 2026 (18 months).
* **Data Nature:** Synthetic operational dataset.
* **Currency & Tax Convention:** All monetary values are in **RON (lei), excluding VAT (fără TVA)**. Ensure all UI labels, tooltips, and KPI cards reflect this explicitly.

### Database Tables (13)
* **Organization & Catalog:** `regiuni`, `magazine`, `categorii`, `produse`, `preturi`
* **Customers & Promotions:** `clienti`, `oferte`, `oferte_produse`
* **Sales & Transactions:** `bonuri`, `vanzari`
* **Inventory & Targets:** `receptii`, `magazin_stoc`, `target_lunar`

---

## 3. Mandatory Engineering & Token-Discipline Rules
Follow these rules strictly throughout the session:
1. **Never open or read the raw `.sql` dump directly.** The dump contains bulk `INSERT` statements that waste context tokens. Instead:
   * Extract the archive via terminal.
   * Load the dump into a local SQLite database file (e.g., `data/farmacia.db`).
   * Inspect the database exclusively via schema commands (`sqlite3 data/farmacia.db ".schema"`) and targeted SQL/Python queries.
2. **Explore before designing.** Before writing any backend or frontend application code, run an Exploratory Data Analysis (EDA) script to verify foreign keys, date distributions, null/edge values, and **hidden anomalies or planted business issues** (e.g., sudden store drops, stock-outs, dead stock, negative margins, or underperforming promotions).
3. **Ground every metric in verified SQL.** Never fabricate mock data or hardcode dashboard numbers. Every KPI, chart, and alert must be dynamically computed from SQLite.
4. **Keep code clean and modular.** Avoid boilerplate bloat and redundant comments. Structure the repository cleanly into `/backend` and `/frontend` (plus `/scripts` for DB initialization/EDA).

---

## 4. Technical Stack
* **Database:** SQLite (`data/farmacia.db`), indexed appropriately for fast analytical filtering.
* **Backend:** Python with **FastAPI** (clean REST endpoints, Pydantic response models, parameterized SQL queries).
* **Frontend:** **React** (Vite + Tailwind CSS + a reliable charting library such as Recharts or Apache ECharts).
* **Bonus (Headless AI Analyst):** Programmatic, non-interactive LLM integration in the Python backend to answer ad-hoc natural-language business questions over the SQLite database.

---

## 5. Core Functional Requirements

### A. Global Controls
* Interactive filtering across the dashboard by **Date Range**, **Region** (`regiuni`), **Pharmacy** (`magazine`), and **Category** (`categorii`), with sensible defaults covering the dataset window.

### B. Business Views & Analytics
1. **Executive Overview (What & When)**
   * Headline KPIs: Total Revenue (RON, ex-VAT), Units Sold, Total Receipts (`bonuri`), Average Basket Value (AOV), Target Attainment %.
   * Time-series revenue & transaction trends (monthly/weekly) showing seasonality and period-over-period growth.
   * Category mix and Top/Bottom performing products.
2. **Geographic & Store Performance (Where)**
   * Regional performance breakdown and store-by-store comparison across all 21 pharmacies.
   * Actual Revenue vs. `target_lunar` attainment (% achieved, variance in RON), clearly flagging stores ahead of or behind target.
3. **Promotions & Customer Insights**
   * Effectiveness of active/historical campaigns (`oferte`, `oferte_produse`): revenue share, uplift, and whether discounts erode value or drive volume.
   * Customer insights (`clienti` linked to `bonuri`): repeat vs. one-time buyers, average spend, top segments.
4. **Operational Problems & Recommended Actions (Priority Differentiator)**
   * Surface real, data-backed operational issues discovered in the database, such as:
     * **Stock-out Risks:** High-velocity products with zero or critically low `magazin_stoc`.
     * **Dead / Slow-Moving Stock:** Capital tied up in inventory with little to no recent sales.
     * **Target Misses & Anomalies:** Pharmacies experiencing sharp revenue drops or chronic underperformance against `target_lunar`.
     * **Supply / Reception Gaps:** Irregularities in `receptii` relative to demand.
   * Pair every detected problem with a clear severity level and a concrete recommended action (e.g., *restock transfer*, *promo review*, *store audit*).

---

## 6. Bonus Requirement: Headless AI Analyst ("Ask Your Data")
Implement an interactive Q&A panel in the React UI backed by a headless LLM endpoint in Python:
* **Execution Mode:** Invoke the model programmatically in headless/non-interactive mode (e.g., `claude -p` CLI, headless Gemini CLI, or an official Python SDK such as `google-genai` / `anthropic` configured via environment variable).
* **Workflow (Text-to-SQL):**
  1. Receive a natural-language question from the frontend.
  2. Supply the exact SQLite schema (plus currency/date conventions) to the model to generate a single SQL query.
  3. **Strict Safety Guardrail:** Enforce read-only execution (`SELECT` / `WITH` statements only; open SQLite in read-only URI mode `file:...?mode=ro`; reject mutating keywords).
  4. Execute the query (with one automatic self-correction retry if SQLite returns a syntax error).
  5. Synthesize a concise, executive-ready answer in plain language and return the answer, the executed SQL (collapsible in UI), and a preview table of the results.

---

## 7. Final Deliverables Checklist
1. Complete working application (`/backend`, `/frontend`, DB setup script, and a concise `README.md` with exact run instructions).
2. Full exported conversation log with the AI harness.
3. Short reflection document (`FUTURE_IMPROVEMENTS.md` or section in `README.md`) outlining what additional features, optimizations, or evaluations would be built given more time or token budget.