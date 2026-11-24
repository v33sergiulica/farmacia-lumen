# Antigravity Harness Conversation ? Farmacia Lumen

---

## User

"$603ff86f-ef82-4483-ac90-c6b4495422b0
Excellent Phase 1 findings. Let's keep Phase 2 strictly to Architecture, Database Indexing, and KPI Specification — do NOT write backend or frontend application code yet.
Design the full-stack architecture (FastAPI + SQLite + React/Vite) and KPI contract so the dashboard directly surfaces the real issues we just uncovered:
1. Data Hygiene & Edge-Case Rules (bake into all SQL queries):
   - Exclude `oferte.id = 13` ("TEST - nu folosi") from campaign KPIs (or flag it separately in data quality notes).
   - Handle returns (`cantitate < 0`) cleanly: report Net Revenue, Gross Profit, Margin %, and explicit Return Rate rather than silently mixing returns into promo/price anomalies.
   - Exclude inactive SKU #180 (`activ = 0`) from active stockout alerts.
   - Account for partial-period stores (`Deva #16` closed 2026-06-30, `Cluj Mărăști #18` opened 2026-03-16) so store comparisons support both total and active-month normalized metrics.
2. Performance & Indexing Plan:
   - Specify the exact read-only analytical indexes to add to `data/farmacia.db` (e.g., on `bonuri`, `vanzari`, `receptii`) via a repeatable script (`scripts/create_indexes.py`) so filtered queries across 674k rows stay sub-100ms.
3. Dashboard Pages & Actionable Modules:
   - Executive Overview (chain KPIs, revenue vs. target attainment trend, structural target bias visibility, Aug 2025 repricing annotation).
   - Store & Region Performance (flagging Constanța Tomis Nord #9's post-Nov 10 collapse, Galați #11's Aug 2025 22-day outage, and Deva/Cluj portfolio transitions).
   - Promotions & Margin Lab (highlighting below-cost 2+1 campaigns, `Somn liniștit` net loss, and YoY `Vara în siguranță` -15% vs -20% profit erosion).
   - Inventory & Restock Risk (prioritized stockout queue ranked by 90-day revenue at risk — surfacing high-ticket SKUs like `Tensiometru` and early-week delivery cadence clustering).
   - Customer & Loyalty View (46% penetration vs. flat AOV/margin and dormant/1-visit member counts).
   - Problems & Recommended Actions Feed (auto-generated, data-backed alerts with quantified RON impact) + planned slot for the Phase 5 Headless AI Analyst ("Ask Your Data").
Output:
- Exact folder structure
- Exact index DDL list
- REST API endpoint contract (routes, query params for global filters: date range, region, store, category, and response shapes)
- Frontend view & chart library choices
Wait for my approval before scaffolding or writing application code.

---

## User

"$603ff86f-ef82-4483-ac90-c6b4495422b0
Approved — this architecture, indexing plan, and API contract are solid. Let's execute **Phase 3 (Database Setup, Indexing, and FastAPI Backend)** only. Do NOT scaffold or write any frontend code yet.
Include these three guardrails during implementation:
1. Inventory Snapshot Semantics: `/api/v1/inventory` must apply `region_id`, `store_id`, `category_id`, and `subcategory_id`, but explicitly ignore `start_date`/`end_date` (return `date_filter_ignored: true`, anchor `snapshot_date` to `2026-10-31` and 90-day velocity to the 90 days ending `2026-10-31`).
2. Dynamic Alerts: Every alert in `/api/v1/alerts` must be computed dynamically via SQL queries against SQLite (no hardcoded Phase 1 numbers or static strings).
3. Evaluator Reproducibility: `scripts/setup_db.py` should cleanly rebuild `data/farmacia.db` from `problema2_database.sql.tar.gz` if missing (with `--force` option), and `scripts/create_indexes.py` should be idempotent.
Execution steps for Phase 3:
1. Build `scripts/setup_db.py` and `scripts/create_indexes.py`, run `create_indexes.py` on `data/farmacia.db`, and print benchmark timings (ms) for key queries to verify sub-100ms performance.
2. Create the Python virtual environment / `backend/requirements.txt` and implement the FastAPI backend (`backend/app/...`) opening SQLite strictly in read-only URI mode (`mode=ro`) for all `/api/v1/*` endpoints except `/api/v1/analyst/ask` (leave a clean stub or defer Phase 5).
3. Write and run a backend verification script (`scripts/verify_api.py` or `pytest` suite using FastAPI `TestClient`) that:
   - Calls every endpoint with default filters and with combined filters (date range, region, store, L1 category, L2 subcategory).
   - Verifies that chain totals from `/api/v1/overview` match our exact Phase 1 numbers (Net Revenue `47,680,504.42 RON`, Gross Profit `15,052,057.43 RON`, Target `50,317,000.00 RON`, Receipts `459,959`).
   - Verifies edge cases: `target_available: false` under category filter, `oferte.id = 13` excluded from active promos, inactive SKU #180 excluded from stockout queue, and zero 500 errors.
Print the index benchmark timings and the full API verification summary, then wait for my review before Phase 4 (Frontend).

---

## User

&"$603ff86f-ef82-4483-ac90-c6b4495422b0
Phase 3 correctness and guardrails look great, but looking at the benchmark table, three default unfiltered endpoints are too slow for a snappy dashboard UX:
- /api/v1/alerts (5.3s)
- /api/v1/customers (3.9s)
- /api/v1/overview (2.0s)
Before we start Phase 4, run a focused optimization pass on the backend only:
1. Reduce redundant full-table scans in `alerts.py`, `customers.py`, and `overview.py` (e.g., combine CTEs/single-pass aggregations where clean, or add a covering index if EXPLAIN QUERY PLAN shows a table scan).
2. Because `data/farmacia.db` is strictly read-only, add a lightweight, bounded in-memory LRU cache (e.g., max 256 entries keyed by endpoint + normalized filter params) for analytical GET responses, and optionally warm the default unfiltered views asynchronously during FastAPI lifespan startup.
3. Re-run `scripts/verify_api.py` to confirm all Phase 1 invariants still match 100%, and report both cold-cache and warm-cache latencies.
Wait for my confirmation before touching the frontend.

---

## User

1"$603ff86f-ef82-4483-ac90-c6b4495422b0
9The backend optimization numbers and verification results look great — Phase 3 is signed off. Now let's execute **Phase 4 (React + TypeScript + Vite + Tailwind + Recharts Frontend)** only. Do NOT implement the Phase 5 LLM backend yet (keep the "Ask Your Data" drawer wired as a clean UI slot ready for Phase 5).
### DESIGN SYSTEM & VISUAL CRAFT (Apothecary Executive BI)
Define clean CSS/Tailwind design tokens first and enforce every rule strictly across all views:
1. Pharmacy Green Palette & High Contrast:
   - Canvas: `#F6F7F6` (subtle neutral-alabaster), elevated data surfaces: `#FFFFFF`, crisp hairline borders: `1px solid #E2E7E4` (use borders + spacing instead of heavy drop shadows).
   - Text contrast (WCAG AA+): primary ink `#111A16`, secondary `#46544D`, muted labels `#5C6B63` (never washed-out light gray).
   - Primary Pharmacy Accent: deep apothecary green `#146C43` (hover `#0F5132`, subtle active tint `#ECF6F0`). Use it with restraint for active nav indicators, primary chart series, focus rings, and the primary CTA.
   - Semantic Signals: reserve crimson `#B42318` (tint `#FEF3F2`) and amber `#B54708` (tint `#FFFAEB`) strictly for target misses, margin losses, stockouts, and high/critical alerts. Keep comparison/baseline series in neutral slate (`#94A3B8`).
2. Anti-Slop Visual Rules (apply everywhere):
   - Delete filler badges & embellishments: NO decorative status pills ("Live", "AI-Powered", "Analytics"), NO gradients, NO glowing/heavy shadows (`shadow-lg`/`shadow-xl`), NO emojis in headings/tabs/badges, NO icons stuck inside pastel circles on KPI cards, and NO random italicized words.
   - Drop redundant labels: don't repeat words the section header or column already states (e.g., avoid repeating "Total" or "Revenue:" inside every card/cell).
   - Typography, Tabular Nums & Mono discipline: load `Inter` (or `IBM Plex Sans`) for all UI and data text, apply `tabular-nums` (`font-variant-numeric: tabular-nums`) to every metric, percentage, axis tick, tooltip, and right-aligned numeric table cell. Reserve monospace (`IBM Plex Mono` / `JetBrains Mono`) ONLY where strictly needed (SQL blocks in the Analyst drawer, SKU/ID codes, raw ISO dates).
   - Headlines & optical craft: make section/chart headlines specific and insight-oriented (e.g., "Monthly Revenue vs. Target (RON fără TVA)" or "Store #9 Post-Nov 2025 Trajectory"), apply `text-balance` for clean wrapping, and align icons/metrics/units optically by baseline rather than raw box centering.
   - Concentric radii (`inner = outer - padding`): maintain consistent radius math across containers and nested controls (e.g., `rounded-lg` [8px] outer card with `p-1` [4px] → `rounded` [4px] inner active tab/pill).
   - Hierarchy & spacing: show real data above the fold immediately (no marketing welcome banner), make the primary chart/table the largest visual anchor on each page, group related metrics with whitespace rather than nested cards-in-cards, and keep icons uniform (`lucide-react`, consistent size and `1.5` stroke width).
   - CTA & purposeful micro-feedback: emphasize ONE clear primary CTA in the header (`Ask Your Data`, solid `#146C43`) and clean contextual action links on the Actions page. Animate only useful feedback (crisp 150ms drawer slide, hover/active filter states, subtle top loading bar on refetch — no gratuitous bounce or page-entrance animations).
### ENGINEERING & UX REQUIREMENTS
1. Stack & Setup:
   - Scaffold `frontend/` with Vite + React + TypeScript + Tailwind CSS + Recharts + `@tanstack/react-query` + `lucide-react`.
   - Configure `vite.config.ts` to proxy `/api` to `http://localhost:8000`.
   - Define strict TypeScript interfaces in `frontend/src/types/api.ts` mirroring our verified FastAPI schemas.
2. Progressive Loading & Resilience (TanStack Query):
   - Configure `QueryClient` with `staleTime: Infinity` (static read-only DB) and `retry: 1`.
   - Never block the app shell: render Sidebar, Header, and Global Filter Bar immediately, with layout-matched skeleton loaders per KPI strip, chart, and table.
   - Use `placeholderData: keepPreviousData` on filter-driven queries with a subtle loading bar / opacity cue so changing filters never flashes blank screens.
   - Silently prefetch default views (`/alerts`, `/stores`, `/promotions`, `/inventory`, `/customers`) in the background after mount so tab switching is instant.
   - Wrap views/panels in an Error Boundary and isolated error states with a working "Retry" button so one failing panel never breaks the rest of the dashboard.
3. Global Filters & Data-Honesty UX:
   - Sync global filters (`start_date`, `end_date`, `region_id`, `store_id`, `category_id`, `subcategory_id`) with URL search params (`FilterContext`).
   - Anchor relative date presets ("Full 18M", "Last 90 Days", "Last 30 Days", "2026 YTD", "Q3 2026") strictly to `2026-10-31` (DB max date), never `new Date()`.
   - Clearly label monetary values as `RON (fără TVA)` across headers, axes, and tooltips.
   - When `target_available === false` (category/subcategory filter active), display a clean inline note instead of `0%` or broken target visuals.
   - On Inventory, display a clear banner: `Snapshot as of 2026-10-31 — date range filter does not apply`.
4. Chart Craft (Recharts):
   - High data-ink ratio: horizontal dashed hairline gridlines only (`#E2E7E4`), no vertical gridlines, no outer chart box, clean `ReferenceLine` / `ReferenceArea` annotations for real events (Aug 2025 repricing wave, Nov 10 Constanța #9 inflection, Galați Aug 2025 outage), and sharp high-contrast tooltips always displaying `RON fără TVA`.
5. Implement All 6 Dashboard Views + Phase 5 Drawer Slot:
   - Executive Overview (KPIs, prominent Revenue vs. Target `ComposedChart` with annotations, Category Mix, Top/Bottom SKUs).
   - Stores & Regions (Regional attainment chart, 21-store leaderboard with Total vs. Normalized/Active-Month toggle + lifecycle indicators, interactive Store Drilldown Drawer showing Constanța #9 vs #10, Galați #11 outage, Cluj #17 vs #18, Deva #16 transfers).
   - Promotions & Margin Lab (Promo KPIs, Revenue Uplift vs. Profit Uplift chart exposing below-cost 2+1 campaigns, side-by-side YoY `Vara în siguranță` -15% vs -20% comparison, muted hygiene note for excluded `ID 13: TEST - nu folosi`).
   - Inventory & Restock Risk (Snapshot KPIs, Store Delivery-Cadence vs. Zero-Stock chart, Priority Restock Queue ranked by 90-day Revenue at Risk with suggested transfer store, Slow-Movers table).
   - Customers & Loyalty (Card vs. No-Card AOV/margin comparison, frequency distribution calling out dormant/1-visit cohorts, demographic charts).
   - Problems & Recommended Actions Command Center (Severity filter controls, quantified RON impact cards, root-cause evidence, concrete action recommendations, and one-click deep links navigating to the relevant view with filters pre-applied).
   - Header "Ask Your Data" button opening `AnalystDrawer.tsx` (Phase 5 UI shell ready to call `POST /api/v1/analyst/ask`).
Verification before stopping:
- Run `npm run build` (TypeScript type-check + Vite production build) and fix all errors/warnings.
- Start backend and frontend briefly and verify all 6 routes load cleanly with zero console errors or broken API bindings.
- Print the build output and verification summary, then wait for my visual inspection before starting Phase 5 (Headless AI Analyst).

---

## User

A"$603ff86f-ef82-4483-ac90-c6b4495422b0
Visual inspection of Phase 4 looks very strong overall — great layout, palette, and speed. Before we commit Phase 4 and move to Phase 5, fix these 5 small bugs/polish items spotted during live testing:
1. Date Input Bug (`FilterBar.tsx`): Typing a year into the `<input type="date">` fields currently fires `onChange` on the first digit (producing `0001` / `0009` and triggering `start_date <= end_date` API errors). Fix this by storing local draft strings in `FilterBar`, setting `min="2025-05-01"` and `max="2026-10-31"`, and only committing to `FilterContext` when a valid complete date within bounds is entered (on `onBlur`, `Enter`, or picker selection).
2. Inventory Chart Axes (`InventoryPage.tsx`): Add `allowDecimals={false}` to the Zero-Stock chart `<YAxis>` so it never shows `0.75`/`1.5`/`2.25` SKUs, and increase bottom chart margin / XAxis `height` so rotated pharmacy names + delivery dates are never clipped.
3. Compact Chart Legends (`CustomersPage.tsx`, `StoresPage.tsx`): Add a clean, minimal inline legend (top-right of chart header) for:
   - Monthly Card vs. Non-Card AOV (solid green = Loyalty Card, dashed slate = Non-Card).
   - Store Drilldown Drawer chart (clearly labeling Store Revenue, Target when `target_available`, and Sibling Store benchmark; omit "vs. Target" from the drawer title when a category filter disables targets).
4. Alerts Math & Date Accuracy (`backend/app/routers/alerts.py`):
   - Fix the `Somn liniștit 2+1` alert `ron_impact`: it currently displays `10,817 RON`, which appears to double-count net profit loss (`4,507`) + below-cost line loss (`6,310`). Use a single non-overlapping impact metric (e.g., `6,310 RON` below-cost loss or `4,507 RON` net loss) and state clearly what it measures.
   - Verify why the Constanța Tomis Nord inflection detection printed `starting 2025-09` instead of `2025-11` (our Phase 1 EDA showed the step-down started Nov 10, 2025) and tighten the inflection check so it identifies the true break month (`2025-11`).
5. Re-run `scripts/verify_api.py` and `npm.cmd run build` to confirm everything passes cleanly.

---

## Assistant

All 5 polish items are fixed and verified:

1. **Date Input Draft & Bounds ([FilterBar.tsx](file:///c:/Users/noemi/Desktop/farmacia-lumen/frontend/src/components/FilterBar.tsx)):**
   - Added local `draftStart` / `draftEnd` state with `min="2025-05-01"` and `max="2026-10-31"`.
   - Partial/invalid keystrokes (like `0001` / `0009`) are ignored; `FilterContext` updates only on valid complete dates within bounds (`start <= end`), and `onBlur` / `Enter` reverts invalid drafts cleanly.

2. **Inventory Chart Axes ([InventoryPage.tsx](file:///c:/Users/noemi/Desktop/farmacia-lumen/frontend/src/pages/InventoryPage.tsx)):**
   - Added `allowDecimals={false}` on the Zero-Stock `<YAxis>` so ticks are strictly integer SKU counts.
   - Expanded container height (`h-96`), bottom margin (`52`), and XAxis `height={92}` (`angle={-32}`) so rotated pharmacy names + delivery dates never clip.

3. **Compact Inline Chart Legends ([CustomersPage.tsx](file:///c:/Users/noemi/Desktop/farmacia-lumen/frontend/src/pages/CustomersPage.tsx), [StoresPage.tsx](file:///c:/Users/noemi/Desktop/farmacia-lumen/frontend/src/pages/StoresPage.tsx)):**
   - Added a minimal inline legend in the Monthly AOV chart header (`Loyalty Card` solid `#146C43`, `Non-Card` dashed `#94A3B8`).
   - Added an inline legend in the Store Drilldown Drawer (`Store Revenue`, `Target` only when targets are available, and `Sibling Store` when present) and omitted `"vs. Target"` from the title whenever category filters disable targets.

4. **Alerts Math & True Inflection Month ([alerts.py](file:///c:/Users/noemi/Desktop/farmacia-lumen/backend/app/routers/alerts.py), [stores.py](file:///c:/Users/noemi/Desktop/farmacia-lumen/backend/app/routers/stores.py)):**
   - Removed double-counting on `Somn liniștit 2+1` (`promo-loss-9`): `ron_impact` now reports only the non-overlapping below-cost line loss (`6,310 RON`), clearly labeled alongside the `-4,507 RON` net profit figure.
   - Tightened step-down detection in both `alerts.py` and `stores.py` (`get_store_trend`) to require an actual month-to-month drop (`prev >= 85%`, `curr < 80%`) and select the split maximizing `avg_before - avg_after`, pinpointing **`2025-11`** for Constanța Tomis Nord (#9).

5. **Verification Passed:**
   - **[scripts/verify_api.py](file:///c:/Users/noemi/Desktop/farmacia-lumen/scripts/verify_api.py):** Exit code `0` — all Phase 1 totals, cold/warm parity (`4.9–9.7 ms` warm), and new regression assertions (`starting 2025-11`, `t9` event `date == "2025-11"`, `somn_alert["ron_impact"] < 7000`) passed.
   - **Frontend Build (`npm.cmd run build`):** `tsc -b && vite build` exited with code `0` in **6.49s** with zero errors or warnings.

Ready whenever you want to move to **Phase 5 (Headless AI Analyst + Documentation Deliverables)**.

---

## User

F"$603ff86f-ef82-4483-ac90-c6b4495422b0
Visual inspection and Phase 4 fixes passed — ready for **Phase 5 (Bonus: Headless AI Analyst — "Ask Your Data")**.
Security hygiene rule: `.env` is already configured locally with `ANALYST_PROVIDER=gemini_api` and `GEMINI_API_KEY`. Do NOT read, print, or echo `.env` or any API key values into your output or logs.
Implement `POST /api/v1/analyst/ask` and wire it end-to-end with `AnalystDrawer.tsx`:
1. Configurable Headless Provider (`backend/app/services/analyst.py`, `backend/app/config.py`, `.env.example`):
   - Load settings cleanly from `.env` via `pydantic-settings` (`ANALYST_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL` defaulting to a fast current Gemini Flash model, plus optional `CLAUDE_CLI_BIN` / `GEMINI_CLI_BIN`).
   - Support three providers: `gemini_api` (using the official `google-genai` SDK — default), `gemini_cli` (headless CLI subprocess), and `claude_cli` (`claude -p` subprocess). Document all three in `.env.example` without secrets.
   - If credentials/CLI are missing, return a clear, non-500 structured error so the UI guides setup gracefully.
2. Domain-Grounded Text-to-SQL Prompting:
   - Inject the exact compact SQLite schema (`CREATE TABLE` definitions) plus our verified business rules into the system prompt:
     - All monetary figures are `RON (fără TVA)`.
     - Exclude `oferte.id = 13` ("TEST - nu folosi") from campaign analytics unless explicitly asked about test data.
     - Returns have `cantitate < 0` (net revenue = `SUM(valoare_fara_tva)`, below-cost promo checks require `cantitate > 0 AND profit < 0`).
     - Inactive SKU `#180` (`activ = 0`) and closed store Deva `#16` (`inchis_la IS NOT NULL`) are excluded from active stockout queries.
     - `magazin_stoc` is a snapshot as of `2026-10-31`.
   - Pass active dashboard `filters` (if any) as optional context so questions like "top 5 products here" respect the user's current view.
3. Strict Read-Only Execution & Safety Guardrails:
   - Validate generated SQL before execution: allow ONLY a single `SELECT` or `WITH ... SELECT` statement; reject multiple statements (`;`), `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `ATTACH`, `DETACH`, `PRAGMA`, `VACUUM`, or write keywords.
   - Execute strictly on our `mode=ro` + `PRAGMA query_only = ON` SQLite connection with a hard row cap (max 200 returned rows) and query timeout.
   - Implement 1x automatic self-correction retry if SQLite raises an execution/syntax error (sending the error message back to the LLM to repair the SQL), returning `retries_used` in the response.
   - Summarize the executed rows back into a concise, business-ready natural-language answer citing exact `RON (fără TVA)` numbers, alongside `sql`, `columns`, `rows`, `row_count`, and `execution_ms`.
4. Frontend Integration (`AnalystDrawer.tsx`):
   - Include 4–5 realistic one-click starter questions that highlight real insights in our dataset (e.g., Constanța Tomis Nord shortfall, worst margin-eroding promotions, top high-risk stockouts, loyalty AOV comparison).
   - Render the natural-language answer cleanly, with a collapsible monospace SQL block (with copy button), compact tabular preview of returned rows, execution timing, and clean loading/error states.
5. Verification & Security Tests (`scripts/verify_analyst.py`):
   - Add automated tests verifying that malicious/write SQL attempts (`DROP TABLE`, `ATTACH DATABASE`, stacked `; DELETE`, `PRAGMA`) are strictly blocked before touching SQLite.
   - Run 3 real business questions end-to-end against `POST /api/v1/analyst/ask` using the configured `.env` provider and verify the numbers match Phase 1 ground truth.
   - Run `npm.cmd run build` in `frontend/` to confirm zero TypeScript/Vite errors.
Report test results and wait for my review before our final Phase 6 wrap-up (`README.md`, `FUTURE_IMPROVEMENTS.md`, and final QA pass).

---

## User

R"$603ff86f-ef82-4483-ac90-c6b4495422b0
The verification run hung for several minutes so I cancelled it. Do NOT blindly re-run it yet.
1. Inspect `backend/app/services/analyst.py` and `scripts/verify_analyst.py` to identify what could hang:
   - Ensure SQLite enforces a real query execution timeout (e.g., 10 seconds via `conn.set_progress_handler`) — not just a connection lock timeout.
   - Ensure the `google-genai` client sets an explicit HTTP timeout (e.g., 25s) and uses a valid, fast Gemini Flash model (no silent infinite retries on 429).
   - In `scripts/verify_analyst.py`, disable startup cache warmup (`warm_cache_on_startup = False`) and add a small 2–3s pause between live LLM test calls so we don't burst free-tier RPM limits.
   - Add flushed step-by-step print statements (`flush=True`) before each test (security checks, then Q1, Q2, Q3) and run with `python -u scripts/verify_analyst.py`.
2. Fix any hang/timeout gap you find, run `python -u scripts/verify_analyst.py` and `npm.cmd run build`, and report the exact output and timings.

---

## User

b"$603ff86f-ef82-4483-ac90-c6b4495422b0
Phase 5 passed verification and live UI testing — ready for **Phase 6 (Quick Launcher, README, Repo Hygiene & Minor Polish)** to wrap up the project cleanly.
Security hygiene rule: Do NOT read, print, or include `.env` or any API keys anywhere.
Deliverables:
1. One-Command Dev Launcher (`scripts/dev.py`):
   - Create a small, clean, cross-platform Python launcher (`python scripts/dev.py`) that:
     - Checks if `data/farmacia.db` exists; if missing and `problema2_database.sql.tar.gz` is present, automatically runs `scripts/setup_db.py` first (otherwise prints a clear instruction).
     - Starts the FastAPI backend (`uvicorn` on `127.0.0.1:8000`) and Vite frontend (`npm.cmd run dev` on Windows to avoid PowerShell execution policy issues, `npm run dev` on macOS/Linux) concurrently.
     - Prints the exact local URLs (`http://127.0.0.1:5173` and `http://127.0.0.1:8000/docs`) and terminates both child processes cleanly on `Ctrl+C`.
2. Two Quick Polish & Hardening Tweaks (keep changes minimal):
   - **`frontend/src/components/AnalystDrawer.tsx`:** Wrap the SQL preview table in a clean `overflow-x-auto` container with `whitespace-nowrap` on `<th>`/`<td>` cells (and widen the drawer slightly if helpful) so wide multi-column results scroll horizontally without wrapping pharmacy names across 5 lines or clipping the rightmost column.
   - **`backend/app/services/analyst.py`:** Quick safety check — confirm CLI providers (`gemini_cli`, `claude_cli`) use `shell=False` and pass prompts safely (e.g., via stdin or `--` separator so user input starting with `-` can't inject flags), and block `zeroblob`/`randomblob` in the SQL validator to prevent memory-exhaustion queries.
3. Repository Hygiene (`.gitignore`):
   - Ensure `.gitignore` cleanly ignores `.env`, `*.tar.gz`, `data/*.db`, `data/*.db-*`, `.venv/`, `__pycache__/`, `frontend/node_modules/`, `frontend/dist/`, and `*.tsbuildinfo`.
   - Confirm via `git status` and `git ls-files` that no secrets, database binaries, or build caches are tracked.
4. Clean, Readable `README.md`:
   - Keep it crisp, scannable, and evaluator-friendly (no bloated fluff):
     - **Project Presentation:** Short summary of the Farmacia Lumen Executive BI platform, its 6 views, and the Apothecary Executive BI design philosophy, plus a clean ASCII architecture diagram (`SQLite mode=ro` → `FastAPI + Bounded LRU Cache` → `React/TanStack Query/Recharts` + `Headless Text-to-SQL Analyst`).
     - **Quickstart (Fastest Path):** Prerequisites, `pip install` + `npm.cmd install`, dropping `problema2_database.sql.tar.gz` in the project root, and launching everything with `python scripts/dev.py` (plus the 2-terminal manual fallback).
     - **AI Analyst Setup:** Short guide to copying `.env.example` → `.env` for `gemini_api`, `gemini_cli`, or `claude_cli`.
     - **Key Business Findings (RON fără TVA):** A concise, high-signal table of the verified insights surfaced by the dashboard (Constanța Tomis Nord post-Nov 2025 collapse, Galați Aug 2025 outage, Deva closure & Cluj Mărăști opening, `Somn liniștit 2+1` net loss & `Vara în siguranță` YoY margin erosion, weekly delivery stockout clustering, loyalty flat AOV & 0/1-visit cohort, plus excluded data hygiene records `oferte.id = 13` and inactive SKU `#180`).
     - **Verification & Performance:** Exact commands (`scripts/verify_api.py`, `scripts/verify_analyst.py`, `npm.cmd run build`) and key cold vs. warm latency numbers.
5. Final Verification:
   - Run `python scripts/verify_api.py`, the non-LLM security tests from `scripts/verify_analyst.py`, and `cd frontend && npm.cmd run build`.
   - Test `scripts/dev.py` briefly (or dry-verify imports/syntax) and print `git status` so I can make the final commit.
