"""Comprehensive FastAPI TestClient verification suite for Phase 3."""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.db import get_ro_connection  # noqa: E402
from backend.app.main import app  # noqa: E402


def timed_get(client: TestClient, path: str, params: dict | None = None) -> tuple[int, dict, float]:
    t0 = time.perf_counter()
    resp = client.get(path, params=params)
    ms = (time.perf_counter() - t0) * 1000.0
    assert resp.status_code < 500, f"5xx error on {path} {params}: {resp.status_code} {resp.text}"
    return resp.status_code, resp.json(), ms


def main() -> None:
    # 0. Verify read-only URI enforcement blocks writes
    conn = get_ro_connection()
    try:
        wrote = False
        try:
            conn.execute("CREATE TABLE _should_fail (id INT)")
            wrote = True
        except sqlite3.OperationalError:
            pass
        assert not wrote, "Read-only SQLite check failed: write succeeded!"
        print("[PASS] Read-only URI mode (mode=ro + query_only=ON) blocks DDL/writes.")
    finally:
        conn.close()

    results: list[tuple[str, int, float]] = []

    with TestClient(app) as client:
        # 1. Health & Filters
        st, health, ms = timed_get(client, "/api/v1/health")
        assert st == 200 and health["db_mode"] == "ro" and health["tables_verified"] == 13
        results.append(("GET /api/v1/health", st, ms))

        st, flt, ms = timed_get(client, "/api/v1/filters")
        assert st == 200 and len(flt["regions"]) == 8 and len(flt["stores"]) == 21 and len(flt["categories"]) == 6
        results.append(("GET /api/v1/filters", st, ms))

        # Look up an L2 subcategory dynamically (e.g. Tensiometre under Dispozitive medicale)
        l1_dermato = next(c for c in flt["categories"] if "Dermato" in c["nume"])
        l2_tensiometre = next(
            sc
            for c in flt["categories"]
            for sc in c["subcategories"]
            if "Tensiometre" in sc["nume"]
        )

        # 2. Overview Default Totals (must match Phase 1 EDA numbers)
        st, ov, ms = timed_get(client, "/api/v1/overview")
        assert st == 200
        k = ov["kpis"]
        assert k["net_revenue_ron"] == 47680504.42, f"Unexpected net_rev: {k['net_revenue_ron']}"
        assert k["gross_profit_ron"] == 15052057.43, f"Unexpected profit: {k['gross_profit_ron']}"
        assert k["target_ron"] == 50317000.00, f"Unexpected target: {k['target_ron']}"
        assert k["receipts"] == 459959, f"Unexpected receipts: {k['receipts']}"
        assert round(k["attainment_pct"], 2) == 94.76, f"Unexpected attainment: {k['attainment_pct']}"
        assert k["return_lines"] == 2009, f"Unexpected return_lines: {k['return_lines']}"
        assert k["target_available"] is True
        assert len(ov["series"]) == 18
        results.append(("GET /api/v1/overview (default 18M)", st, ms))
        print("[PASS] Phase 1 chain totals verified on /api/v1/overview (47,680,504.42 RON | 15,052,057.43 profit | 50,317,000.00 target | 459,959 receipts).")

        # Weekly granularity
        st, ov_w, ms = timed_get(client, "/api/v1/overview", {"granularity": "week"})
        assert st == 200 and len(ov_w["series"]) > 70
        results.append(("GET /api/v1/overview (weekly)", st, ms))

        # Overview with Category L1 & L2 filters -> target_available must be False
        st, ov_c1, ms = timed_get(client, "/api/v1/overview", {"category_id": l1_dermato["id"]})
        assert st == 200 and ov_c1["kpis"]["target_available"] is False and ov_c1["kpis"]["target_ron"] is None
        assert ov_c1["kpis"]["net_revenue_ron"] == 14322841.23
        results.append(("GET /api/v1/overview (L1 category)", st, ms))

        st, ov_c2, ms = timed_get(client, "/api/v1/overview", {"subcategory_id": l2_tensiometre["id"]})
        assert st == 200 and ov_c2["kpis"]["target_available"] is False and ov_c2["kpis"]["target_ron"] is None
        results.append(("GET /api/v1/overview (L2 subcategory)", st, ms))

        # Combined filters (date + region + store)
        combo_params = {
            "start_date": "2026-01-01",
            "end_date": "2026-06-30",
            "region_id": 3,
            "store_id": 9,
        }
        st, ov_combo, ms = timed_get(client, "/api/v1/overview", combo_params)
        assert st == 200 and ov_combo["kpis"]["target_available"] is True and ov_combo["kpis"]["net_revenue_ron"] > 0
        results.append(("GET /api/v1/overview (date+region+store)", st, ms))

        # Combined filters (date + region + L1 category)
        st, ov_combo2, ms = timed_get(
            client,
            "/api/v1/overview",
            {"start_date": "2025-11-01", "end_date": "2026-10-31", "region_id": 3, "category_id": l1_dermato["id"]},
        )
        assert st == 200 and ov_combo2["kpis"]["target_available"] is False
        results.append(("GET /api/v1/overview (date+region+L1)", st, ms))

        # 3. Stores & Store Trends
        st, stores, ms = timed_get(client, "/api/v1/stores")
        assert st == 200 and len(stores["stores"]) == 21 and len(stores["regions"]) == 8
        s9 = next(s for s in stores["stores"] if s["id"] == 9)
        s16 = next(s for s in stores["stores"] if s["id"] == 16)
        s18 = next(s for s in stores["stores"] if s["id"] == 18)
        assert round(s9["attainment_pct"], 1) == 77.9 and "sustained_underperformance" in s9["anomaly_flags"]
        assert s16["status"] == "closed" and s16["active_months"] == 14
        assert s18["status"] == "opened_mid_period" and s18["active_months"] == 8
        results.append(("GET /api/v1/stores (default)", st, ms))

        st, stores_cat, ms = timed_get(client, "/api/v1/stores", {"category_id": l1_dermato["id"]})
        assert st == 200 and stores_cat["target_available"] is False
        results.append(("GET /api/v1/stores (L1 category)", st, ms))

        st, t9, ms = timed_get(client, "/api/v1/stores/9/trend")
        assert st == 200 and t9["sibling_comparison"] is not None and t9["sibling_comparison"]["store_id"] == 10
        assert any("Step-Down" in e["title"] for e in t9["events"])
        results.append(("GET /api/v1/stores/9/trend", st, ms))

        st, t11, ms = timed_get(client, "/api/v1/stores/11/trend")
        assert st == 200 and any("22-Day" in e["title"] for e in t11["events"])
        results.append(("GET /api/v1/stores/11/trend", st, ms))

        st, t16, ms = timed_get(client, "/api/v1/stores/16/trend")
        assert st == 200 and len(t16["transfers"]) == 3
        results.append(("GET /api/v1/stores/16/trend", st, ms))

        # 4. Promotions (verify oferte.id=13 excluded from active campaigns)
        st, promos, ms = timed_get(client, "/api/v1/promotions")
        assert st == 200
        assert promos["summary"]["active_campaigns"] == 12
        assert all(c["id"] != 13 for c in promos["campaigns"]), "Test promo ID 13 leaked into active campaigns!"
        assert any(tp["id"] == 13 for tp in promos["excluded_test_promos"])
        assert any(c["id"] == 9 and c["verdict"] == "net_loss" and c["profit_ron"] < 0 for c in promos["campaigns"])
        assert len(promos["yoy_comparisons"]) >= 1
        results.append(("GET /api/v1/promotions (default)", st, ms))

        st, promos_f, ms = timed_get(
            client, "/api/v1/promotions", {"region_id": 3, "category_id": l1_dermato["id"]}
        )
        assert st == 200
        results.append(("GET /api/v1/promotions (region+L1)", st, ms))

        # 5. Inventory (date filter ignored, SKU #180 excluded, Deva #16 excluded)
        st, inv_def, ms = timed_get(client, "/api/v1/inventory")
        assert st == 200
        assert inv_def["date_filter_ignored"] is True
        assert inv_def["snapshot_date"] == "2026-10-31"
        assert inv_def["kpis"]["active_zero_stock_pairs"] == 209
        assert inv_def["kpis"]["ledger_discrepancy_units"] == 0
        assert all(item["product_id"] != 180 for item in inv_def["stockout_queue"])
        assert all(item["product_id"] != 180 for item in inv_def["top_stocked_out_skus"])
        assert all(sc["store_id"] != 16 for sc in inv_def["store_cadence"])
        results.append(("GET /api/v1/inventory (default)", st, ms))

        st, inv_narrow, ms = timed_get(
            client,
            "/api/v1/inventory",
            {"start_date": "2025-05-01", "end_date": "2025-05-10"},
        )
        assert st == 200 and inv_narrow["kpis"] == inv_def["kpis"], "Inventory ignored-date invariant failed!"
        results.append(("GET /api/v1/inventory (narrow dates ignored)", st, ms))

        st, inv_reg, ms = timed_get(
            client,
            "/api/v1/inventory",
            {"region_id": 2, "subcategory_id": l2_tensiometre["id"]},
        )
        assert st == 200 and inv_reg["date_filter_ignored"] is True
        results.append(("GET /api/v1/inventory (region+L2)", st, ms))

        # 6. Customers
        st, cust, ms = timed_get(client, "/api/v1/customers")
        assert st == 200 and cust["total_registered_members"] == 26000
        assert cust["dormant_members"] == 1491 and cust["one_time_members"] == 1681
        results.append(("GET /api/v1/customers (default)", st, ms))

        st, cust_f, ms = timed_get(
            client, "/api/v1/customers", {"start_date": "2026-01-01", "end_date": "2026-06-30", "region_id": 3}
        )
        assert st == 200
        results.append(("GET /api/v1/customers (date+region)", st, ms))

        # 7. Alerts (dynamic SQL)
        st, al, ms = timed_get(client, "/api/v1/alerts")
        assert st == 200
        assert al["counts"]["critical"] >= 2
        assert al["counts"]["high"] >= 3
        assert al["counts"]["medium"] >= 2
        assert al["counts"]["low"] >= 1
        results.append(("GET /api/v1/alerts (default)", st, ms))

        st, al_f, ms = timed_get(client, "/api/v1/alerts", {"severity": "critical", "region_id": 3})
        assert st == 200 and all(a["severity"] == "critical" for a in al_f["alerts"])
        results.append(("GET /api/v1/alerts (severity+region)", st, ms))

        # 8. Analyst stub returns 501 (not 500)
        t0 = time.perf_counter()
        resp = client.post("/api/v1/analyst/ask", json={"question": "Top 5 stores?"})
        ms = (time.perf_counter() - t0) * 1000.0
        assert resp.status_code == 501
        results.append(("POST /api/v1/analyst/ask (stub)", resp.status_code, ms))

    print("\nAPI Verification Summary:")
    print(f"  {'Endpoint':<46} {'Status':>6} {'Time (ms)':>10}")
    print("  " + "-" * 66)
    for name, code, ms in results:
        print(f"  {name:<46} {code:>6} {ms:>9.1f}")
    print("\nALL PHASE 3 CHECKS PASSED WITH ZERO 500 ERRORS.")


if __name__ == "__main__":
    main()
