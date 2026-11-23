"""Inventory & Restock Risk endpoints (snapshot anchored to 2026-10-31)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from ..config import settings
from ..db import get_db, query_all, query_one
from ..schemas import (
    InventoryKpis,
    InventoryResponse,
    SlowMoverItem,
    StockedOutSkuSummary,
    StockoutQueueItem,
    StoreCadenceItem,
    TransferSuggestion,
)
from ..services.cache import cached_call, make_cache_key
from ..services.filters import (
    OPEN_STORE_SQL,
    GlobalFilters,
    get_global_filters,
)

router = APIRouter(tags=["inventory"])


def _build_inv_scope(filters: GlobalFilters) -> tuple[str, dict[str, int]]:
    """Apply region, store, category, and subcategory filters; ignore start/end dates."""
    clauses = [OPEN_STORE_SQL]
    params: dict[str, int] = {}
    if filters.region_id is not None:
        clauses.append("m.id_regiune = :region_id")
        params["region_id"] = filters.region_id
    if filters.store_id is not None:
        clauses.append("m.id = :store_id")
        params["store_id"] = filters.store_id
    if filters.subcategory_id is not None:
        clauses.append("p.id_categorie = :subcategory_id")
        params["subcategory_id"] = filters.subcategory_id
    elif filters.category_id is not None:
        clauses.append(
            "p.id_categorie IN (SELECT id FROM categorii WHERE id = :category_id OR id_parinte = :category_id)"
        )
        params["category_id"] = filters.category_id
    return " AND ".join(clauses), params


@router.get("/inventory", response_model=InventoryResponse)
def get_inventory(
    low_stock_max: int = Query(default=5, ge=1, le=20),
    limit: int = Query(default=50, ge=5, le=200),
    filters: GlobalFilters = Depends(get_global_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> InventoryResponse:
    def _compute() -> InventoryResponse:
        return _compute_inventory(low_stock_max, limit, filters, conn)

    return cached_call(
        make_cache_key(
            "inventory",
            filters,
            ignore_dates=True,
            low_stock_max=low_stock_max,
            limit=limit,
        ),
        _compute,
    )


def _compute_inventory(
    low_stock_max: int,
    limit: int,
    filters: GlobalFilters,
    conn: sqlite3.Connection,
) -> InventoryResponse:
    snap_row = query_one(conn, "SELECT substr(cand, 1, 10) AS snap FROM bonuri ORDER BY cand DESC LIMIT 1")
    snapshot_str = snap_row["snap"] if snap_row and snap_row["snap"] else settings.default_end_date
    snapshot_dt = date.fromisoformat(snapshot_str)
    vel_start_dt = snapshot_dt - timedelta(days=89)
    vel_start_str = vel_start_dt.isoformat()
    vel_start_ts = f"{vel_start_str} 00:00:00"
    vel_end_excl_ts = f"{(snapshot_dt + timedelta(days=1)).isoformat()} 00:00:00"
    deliv_30_start = (snapshot_dt - timedelta(days=29)).isoformat()

    scope_sql, scope_params = _build_inv_scope(filters)

    # 1. Compute 90-day velocity ONCE over the 90-day window
    vel_rows = query_all(
        conn,
        """
        SELECT b.id_magazin, v.id_produs,
               SUM(v.cantitate) AS qty_90d,
               SUM(v.valoare_fara_tva) AS rev_90d
        FROM bonuri b
        JOIN vanzari v ON v.id_bon = b.id
        WHERE b.cand >= ? AND b.cand < ?
        GROUP BY b.id_magazin, v.id_produs
        """,
        (vel_start_ts, vel_end_excl_ts),
    )
    vel_map: dict[tuple[int, int], tuple[int, float]] = {
        (int(r["id_magazin"]), int(r["id_produs"])): (int(r["qty_90d"]), float(r["rev_90d"]))
        for r in vel_rows
    }

    # 2. Fetch scoped open-store stock pairs (max 3,600 rows) + current cost
    stoc_rows = query_all(
        conn,
        f"""
        SELECT ms.id_magazin AS store_id, m.nume AS store_name, m.id_regiune, r.nume AS region,
               p.id AS product_id, p.nume AS product_name, p.brand, p.activ,
               c.nume AS category, ms.stoc, cp.cost_achizitie
        FROM magazin_stoc ms
        JOIN magazine m ON m.id = ms.id_magazin
        JOIN regiuni r ON r.id = m.id_regiune
        JOIN produse p ON p.id = ms.id_produs
        JOIN categorii c ON c.id = p.id_categorie
        JOIN preturi cp ON cp.id_produs = p.id AND cp.pana_la IS NULL
        WHERE {scope_sql}
        """,
        scope_params,
    )

    # 3. Delivery cadence per open store (small receptii index scan)
    deliv_rows = query_all(
        conn,
        """
        SELECT id_magazin,
               MAX(data) AS last_delivery_date,
               COUNT(DISTINCT CASE WHEN data >= ? THEN data END) AS recent_delivs
        FROM receptii
        WHERE tip = 'livrare'
        GROUP BY id_magazin
        """,
        (deliv_30_start,),
    )
    deliv_map = {
        int(r["id_magazin"]): (r["last_delivery_date"], int(r["recent_delivs"]))
        for r in deliv_rows
    }

    # 4. Fast chain-wide ledger discrepancy check (uses covering indexes)
    recon = query_one(
        conn,
        """
        SELECT (SELECT COALESCE(SUM(stoc), 0) FROM magazin_stoc)
             - ((SELECT COALESCE(SUM(cantitate), 0) FROM receptii)
                - (SELECT COALESCE(SUM(cantitate), 0) FROM vanzari)) AS diff
        """,
    )
    ledger_diff = abs(int(recon["diff"])) if recon else 0

    # 5. Donors across ALL open stores (stoc >= 6) for transfer suggestions
    donor_rows = query_all(
        conn,
        """
        SELECT ms.id_produs, m.id AS store_id, m.nume AS store_name, m.id_regiune, ms.stoc
        FROM magazin_stoc ms
        JOIN magazine m ON m.id = ms.id_magazin
        WHERE m.inchis_la IS NULL AND ms.stoc >= 6
        ORDER BY ms.id_produs, ms.stoc DESC
        """,
    )
    donors_by_sku: dict[int, list[sqlite3.Row]] = {}
    for d in donor_rows:
        donors_by_sku.setdefault(int(d["id_produs"]), []).append(d)

    # Aggregate everything in Python over <= 3,600 rows
    total_inv_cost = 0.0
    total_units = 0
    active_zero_pairs = 0
    low_pairs = 0
    dead90_pairs = 0
    dead90_cost = 0.0
    rev_at_risk_total = 0.0

    store_acc: dict[int, dict[str, object]] = {}
    sku_acc: dict[int, dict[str, object]] = {}
    zero_candidates: list[tuple[float, int, sqlite3.Row]] = []

    for r in stoc_rows:
        sid = int(r["store_id"])
        pid = int(r["product_id"])
        stoc = int(r["stoc"])
        activ = int(r["activ"]) == 1
        cost = float(r["cost_achizitie"])
        qty_90d, rev_90d = vel_map.get((sid, pid), (0, 0.0))

        total_units += stoc
        total_inv_cost += stoc * cost

        s_entry = store_acc.setdefault(
            sid,
            {
                "store_id": sid,
                "store_name": r["store_name"],
                "region": r["region"],
                "zero": 0,
                "low": 0,
                "risk": 0.0,
            },
        )

        if activ:
            k_entry = sku_acc.setdefault(
                pid,
                {
                    "product_id": pid,
                    "product_name": r["product_name"],
                    "brand": r["brand"],
                    "category": r["category"],
                    "zero_stores": 0,
                    "total_stoc": 0,
                    "inv_cost": 0.0,
                    "qty_90d": 0,
                    "rev_90d": 0.0,
                },
            )
            k_entry["total_stoc"] = int(k_entry["total_stoc"]) + stoc
            k_entry["inv_cost"] = float(k_entry["inv_cost"]) + stoc * cost
            k_entry["qty_90d"] = int(k_entry["qty_90d"]) + qty_90d
            k_entry["rev_90d"] = float(k_entry["rev_90d"]) + rev_90d

            if stoc == 0:
                active_zero_pairs += 1
                rev_at_risk_total += rev_90d
                s_entry["zero"] = int(s_entry["zero"]) + 1
                s_entry["risk"] = float(s_entry["risk"]) + rev_90d
                k_entry["zero_stores"] = int(k_entry["zero_stores"]) + 1
                zero_candidates.append((rev_90d, qty_90d, r))
            elif 1 <= stoc <= low_stock_max:
                low_pairs += 1
                s_entry["low"] = int(s_entry["low"]) + 1

            if stoc > 0 and qty_90d <= 0:
                dead90_pairs += 1
                dead90_cost += stoc * cost

    total_pairs = len(stoc_rows)
    kpis = InventoryKpis(
        total_inv_cost_ron=round(total_inv_cost, 2),
        total_units=total_units,
        open_store_sku_pairs=total_pairs,
        active_zero_stock_pairs=active_zero_pairs,
        low_stock_pairs=low_pairs,
        low_stock_share_pct=round(100.0 * low_pairs / total_pairs, 2) if total_pairs else 0.0,
        dead_stock_90d_pairs=dead90_pairs,
        dead_stock_90d_cost_ron=round(dead90_cost, 2),
        rev_90d_at_risk_ron=round(rev_at_risk_total, 2),
        ledger_discrepancy_units=ledger_diff,
    )

    store_cadence = []
    for sid, s_entry in store_acc.items():
        ld, rec_cnt = deliv_map.get(sid, (None, 0))
        days_since = (snapshot_dt - date.fromisoformat(ld)).days if ld else None
        store_cadence.append(
            StoreCadenceItem(
                store_id=sid,
                store_name=str(s_entry["store_name"]),
                region=str(s_entry["region"]),
                zero_active_skus=int(s_entry["zero"]),
                low_stock_skus=int(s_entry["low"]),
                rev_90d_at_risk_ron=round(float(s_entry["risk"]), 2),
                last_delivery_date=ld,
                days_since_last_delivery=days_since,
                recent_30d_deliveries=rec_cnt,
            )
        )
    store_cadence.sort(key=lambda x: (-x.zero_active_skus, -x.rev_90d_at_risk_ron))

    zero_candidates.sort(key=lambda t: (-t[0], -t[1]))
    stockout_queue: list[StockoutQueueItem] = []
    for rev_90d, qty_90d, r in zero_candidates[:limit]:
        sid = int(r["store_id"])
        pid = int(r["product_id"])
        rid = int(r["id_regiune"])
        candidates = [d for d in donors_by_sku.get(pid, []) if int(d["store_id"]) != sid]
        best_donor = None
        if candidates:
            same_reg = [d for d in candidates if int(d["id_regiune"]) == rid]
            pick = same_reg[0] if same_reg else candidates[0]
            best_donor = TransferSuggestion(
                store_id=int(pick["store_id"]),
                store_name=pick["store_name"],
                available_stoc=int(pick["stoc"]),
                same_region=(int(pick["id_regiune"]) == rid),
            )
        ld, _ = deliv_map.get(sid, (None, 0))
        stockout_queue.append(
            StockoutQueueItem(
                store_id=sid,
                store_name=r["store_name"],
                region=r["region"],
                product_id=pid,
                product_name=r["product_name"],
                brand=r["brand"],
                category=r["category"],
                stoc=0,
                qty_90d=qty_90d,
                rev_90d_at_risk_ron=round(rev_90d, 2),
                last_delivery_date=ld,
                suggested_transfer_from=best_donor,
            )
        )

    top_stocked_out_skus = [
        StockedOutSkuSummary(
            product_id=int(k["product_id"]),
            product_name=str(k["product_name"]),
            brand=str(k["brand"]),
            category=str(k["category"]),
            zero_stores=int(k["zero_stores"]),
            total_stoc=int(k["total_stoc"]),
            qty_90d=int(k["qty_90d"]),
            rev_90d_ron=round(float(k["rev_90d"]), 2),
        )
        for k in sorted(
            [v for v in sku_acc.values() if int(v["zero_stores"]) > 0],
            key=lambda x: (-int(x["zero_stores"]), -float(x["rev_90d"])),
        )[:15]
    ]

    slow_list = []
    for k in sku_acc.values():
        tot_s = int(k["total_stoc"])
        if tot_s <= 0:
            continue
        q90 = int(k["qty_90d"])
        dos = round(tot_s / (q90 / 90.0), 1) if q90 > 0 else None
        slow_list.append(
            SlowMoverItem(
                product_id=int(k["product_id"]),
                product_name=str(k["product_name"]),
                category=str(k["category"]),
                total_stoc=tot_s,
                inv_cost_ron=round(float(k["inv_cost"]), 2),
                qty_90d=q90,
                days_of_supply=dos,
            )
        )
    slow_list.sort(
        key=lambda x: (0 if x.days_of_supply is None else 1, -(x.days_of_supply or 0.0))
    )

    return InventoryResponse(
        currency=settings.currency_label,
        date_filter_ignored=True,
        snapshot_date=snapshot_str,
        velocity_window_start=vel_start_str,
        kpis=kpis,
        store_cadence=store_cadence,
        stockout_queue=stockout_queue,
        top_stocked_out_skus=top_stocked_out_skus,
        slow_movers=slow_list[:15],
    )
