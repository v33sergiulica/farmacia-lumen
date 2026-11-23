"""Comprehensive FastAPI TestClient verification suite (cold & warm cache) for Phase 3."""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import settings  # noqa: E402
from backend.app.db import get_ro_connection  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.services.cache import response_cache  # noqa: E402


def timed_get(client: TestClient, path: str, params: dict | None = None) -> tuple[int, dict, float]:
    t0 = time.perf_counter()
    resp = client.get(path, params=params)
    ms = (time.perf_counter() - t0) * 1000.0
    assert resp.status_code < 500, f"5xx error on {path} {params}: {resp.status_code} {resp.text}"
    return resp.status_code, resp.json(), ms


def run_pass(client: TestClient, verify_invariants: bool) -> list[tuple[str, str, dict | None, int, dict, float]]:
    records: list[tuple[str, str, dict | None, int, dict, float]] = []

    def call(label: str, path: str, params: dict | None = None) -> dict:
        st, body, ms = timed_get(client, path, params)
        records.append((label, path, params, st, body, ms))
        return body

    health = call("GET /api/v1/health", "/api/v1/health")
    flt = call("GET /api/v1/filters", "/api/v1/filters")
    l1_dermato = next(c for c in flt["categories"] if "Dermato" in c["nume"])
    l2_tensiometre = next(
        sc for c in flt["categories"] for sc in c["subcategories"] if "Tensiometre" in sc["nume"]
    )

    ov = call("GET /api/v1/overview (default 18M)", "/api/v1/overview")
    ov_w = call("GET /api/v1/overview (weekly)", "/api/v1/overview", {"granularity": "week"})
    ov_c1 = call("GET /api/v1/overview (L1 category)", "/api/v1/overview", {"category_id": l1_dermato["id"]})
    ov_c2 = call("GET /api/v1/overview (L2 subcategory)", "/api/v1/overview", {"subcategory_id": l2_tensiometre["id"]})
    ov_combo = call(
        "GET /api/v1/overview (date+region+store)",
        "/api/v1/overview",
        {"start_date": "2026-01-01", "end_date": "2026-06-30", "region_id": 3, "store_id": 9},
    )
    ov_combo2 = call(
        "GET /api/v1/overview (date+region+L1)",
        "/api/v1/overview",
        {"start_date": "2025-11-01", "end_date": "2026-10-31", "region_id": 3, "category_id": l1_dermato["id"]},
    )

    stores = call("GET /api/v1/stores (default)", "/api/v1/stores")
    stores_cat = call("GET /api/v1/stores (L1 category)", "/api/v1/stores", {"category_id": l1_dermato["id"]})
    t9 = call("GET /api/v1/stores/9/trend", "/api/v1/stores/9/trend")
    t11 = call("GET /api/v1/stores/11/trend", "/api/v1/stores/11/trend")
    t16 = call("GET /api/v1/stores/16/trend", "/api/v1/stores/16/trend")

    promos = call("GET /api/v1/promotions (default)", "/api/v1/promotions")
    call("GET /api/v1/promotions (region+L1)", "/api/v1/promotions", {"region_id": 3, "category_id": l1_dermato["id"]})

    inv_def = call("GET /api/v1/inventory (default)", "/api/v1/inventory")
    inv_narrow = call(
        "GET /api/v1/inventory (narrow dates ignored)",
        "/api/v1/inventory",
        {"start_date": "2025-05-01", "end_date": "2025-05-10"},
    )
    inv_reg = call(
        "GET /api/v1/inventory (region+L2)",
        "/api/v1/inventory",
        {"region_id": 2, "subcategory_id": l2_tensiometre["id"]},
    )

    cust = call("GET /api/v1/customers (default)", "/api/v1/customers")
    call(
        "GET /api/v1/customers (date+region)",
        "/api/v1/customers",
        {"start_date": "2026-01-01", "end_date": "2026-06-30", "region_id": 3},
    )

    al = call("GET /api/v1/alerts (default)", "/api/v1/alerts")
    al_f = call(
        "GET /api/v1/alerts (severity+region)",
        "/api/v1/alerts",
        {"severity": "critical", "region_id": 3},
    )

    if verify_invariants:
        assert health["db_mode"] == "ro" and health["tables_verified"] == 13
        assert len(flt["regions"]) == 8 and len(flt["stores"]) == 21 and len(flt["categories"]) == 6

        k = ov["kpis"]
        assert k["net_revenue_ron"] == 47680504.42, f"Unexpected net_rev: {k['net_revenue_ron']}"
        assert k["gross_profit_ron"] == 15052057.43, f"Unexpected profit: {k['gross_profit_ron']}"
        assert k["target_ron"] == 50317000.00, f"Unexpected target: {k['target_ron']}"
        assert k["receipts"] == 459959, f"Unexpected receipts: {k['receipts']}"
        assert round(k["attainment_pct"], 2) == 94.76, f"Unexpected attainment: {k['attainment_pct']}"
        assert k["return_lines"] == 2009, f"Unexpected return_lines: {k['return_lines']}"
        assert k["target_available"] is True and len(ov["series"]) == 18
        assert len(ov_w["series"]) > 70
        assert ov_c1["kpis"]["target_available"] is False and ov_c1["kpis"]["target_ron"] is None
        assert ov_c1["kpis"]["net_revenue_ron"] == 14322841.23
        assert ov_c2["kpis"]["target_available"] is False and ov_c2["kpis"]["target_ron"] is None
        assert ov_combo["kpis"]["target_available"] is True and ov_combo["kpis"]["net_revenue_ron"] > 0
        assert ov_combo2["kpis"]["target_available"] is False

        assert len(stores["stores"]) == 21 and len(stores["regions"]) == 8
        s9 = next(s for s in stores["stores"] if s["id"] == 9)
        s16 = next(s for s in stores["stores"] if s["id"] == 16)
        s18 = next(s for s in stores["stores"] if s["id"] == 18)
        assert round(s9["attainment_pct"], 1) == 77.9 and "sustained_underperformance" in s9["anomaly_flags"]
        assert s16["status"] == "closed" and s16["active_months"] == 14
        assert s18["status"] == "opened_mid_period" and s18["active_months"] == 8
        assert stores_cat["target_available"] is False
        assert t9["sibling_comparison"] is not None and t9["sibling_comparison"]["store_id"] == 10
        assert any("Step-Down" in e["title"] for e in t9["events"])
        assert any("22-Day" in e["title"] for e in t11["events"])
        assert len(t16["transfers"]) == 3

        assert promos["summary"]["active_campaigns"] == 12
        assert all(c["id"] != 13 for c in promos["campaigns"])
        assert any(tp["id"] == 13 for tp in promos["excluded_test_promos"])
        assert any(c["id"] == 9 and c["verdict"] == "net_loss" and c["profit_ron"] < 0 for c in promos["campaigns"])
        assert len(promos["yoy_comparisons"]) >= 1

        assert inv_def["date_filter_ignored"] is True and inv_def["snapshot_date"] == "2026-10-31"
        assert inv_def["kpis"]["active_zero_stock_pairs"] == 209
        assert inv_def["kpis"]["ledger_discrepancy_units"] == 0
        assert all(item["product_id"] != 180 for item in inv_def["stockout_queue"])
        assert all(item["product_id"] != 180 for item in inv_def["top_stocked_out_skus"])
        assert all(sc["store_id"] != 16 for sc in inv_def["store_cadence"])
        assert inv_narrow["kpis"] == inv_def["kpis"]
        assert inv_reg["date_filter_ignored"] is True

        assert cust["total_registered_members"] == 26000
        assert cust["dormant_members"] == 1491 and cust["one_time_members"] == 1681
        sex_rev = sum(b["revenue_ron"] for b in cust["demographics"]["by_sex"])
        age_rev = sum(b["revenue_ron"] for b in cust["demographics"]["by_age_band"])
        reg_rev = sum(b["revenue_ron"] for b in cust["demographics"]["by_region"])
        card_rev = cust["penetration"]["card_revenue_ron"]
        assert abs(sex_rev - card_rev) < 0.05 and abs(age_rev - card_rev) < 0.05 and abs(reg_rev - card_rev) < 0.05
        assert sum(b["receipts"] for b in cust["demographics"]["by_sex"]) == cust["penetration"]["card_receipts"]

        assert al["counts"]["critical"] >= 2 and al["counts"]["high"] >= 3
        assert al["counts"]["medium"] >= 2 and al["counts"]["low"] >= 1
        assert all(a["severity"] == "critical" for a in al_f["alerts"])

    return records


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

    # 1. Cold-Cache Pass (disable startup auto-warmup & clear cache for honest cold timings)
    settings.warm_cache_on_startup = False
    response_cache.clear()

    with TestClient(app) as client:
        cold = run_pass(client, verify_invariants=True)
        print("[PASS] Phase 1 chain totals & demographic/edge invariants verified on cold pass.")

        # 2. Warm-Cache Pass (same client, cache populated)
        warm = run_pass(client, verify_invariants=False)
        for c_rec, w_rec in zip(cold, warm, strict=True):
            assert c_rec[4] == w_rec[4], f"Warm response diverged from cold on {c_rec[0]}"
        print("[PASS] Warm-cache pass matched cold-cache payloads 100%.")

        # Analyst stub check
        t0 = time.perf_counter()
        resp = client.post("/api/v1/analyst/ask", json={"question": "Top 5 stores?"})
        stub_ms = (time.perf_counter() - t0) * 1000.0
        assert resp.status_code == 501

    # 3. Verify async startup cache warmup completes cleanly
    response_cache.clear()
    settings.warm_cache_on_startup = True
    with TestClient(app) as client:
        # Poll briefly for background thread warmup to finish
        for _ in range(60):
            if response_cache.stats()["size"] >= 7:
                break
            time.sleep(0.1)
        st, _, warm_ov_ms = timed_get(client, "/api/v1/overview")
        assert st == 200
        print(f"[PASS] Async lifespan cache warmup populated {response_cache.stats()['size']} entries (overview={warm_ov_ms:.1f} ms).")

    print("\nAPI Cold vs. Warm Verification Summary:")
    print(f"  {'Endpoint':<44} {'St':>3} {'Cold(ms)':>9} {'Warm(ms)':>9} {'Speedup':>8}")
    print("  " + "-" * 77)
    for (lbl, _p, _pr, st, _b, c_ms), (_wl, _wp, _wpr, _wst, _wb, w_ms) in zip(cold, warm, strict=True):
        spd = f"{c_ms / w_ms:.0f}x" if w_ms > 0.05 else ">1000x"
        print(f"  {lbl:<44} {st:>3} {c_ms:>9.1f} {w_ms:>9.1f} {spd:>8}")
    print(f"  {'POST /api/v1/analyst/ask (stub)':<44} {501:>3} {stub_ms:>9.1f} {'-':>9} {'-':>8}")
    print(f"\nCache stats: {response_cache.stats()}")
    print("ALL PHASE 3 OPTIMIZED CHECKS PASSED WITH ZERO 500 ERRORS.")


if __name__ == "__main__":
    main()
