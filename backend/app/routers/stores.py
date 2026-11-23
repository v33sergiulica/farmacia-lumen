"""Geographic, Store Performance, and Store Drilldown Trend endpoints."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import settings
from ..db import get_db, query_all, query_one
from ..schemas import (
    RegionPerformance,
    SiblingComparison,
    StoreEvent,
    StorePerformance,
    StoresResponse,
    StoreTransferSummary,
    StoreTrendPoint,
    StoreTrendResponse,
)
from ..services.filters import (
    GlobalFilters,
    build_sales_where,
    compute_targets,
    get_global_filters,
    get_store_trend_filters,
    sales_joins_sql,
)

router = APIRouter(tags=["stores"])


def _store_status(deschis_la: str, inchis_la: str | None) -> Literal["active", "opened_mid_period", "closed"]:
    if inchis_la is not None:
        return "closed"
    if deschis_la > settings.default_start_date:
        return "opened_mid_period"
    return "active"


@router.get("/stores", response_model=StoresResponse)
def get_stores(
    sort_by: Literal[
        "attainment_pct",
        "revenue_ron",
        "rev_per_active_month",
        "rev_per_sqm_month",
        "margin_pct",
    ] = Query(default="attainment_pct"),
    filters: GlobalFilters = Depends(get_global_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> StoresResponse:
    where_sql, params, _, needs_prod, needs_cat = build_sales_where(filters)
    joins_sql = sales_joins_sql(False, needs_prod, needs_cat)

    # Aggregate sales per store in filtered window
    sales_rows = query_all(
        conn,
        f"""
        SELECT b.id_magazin,
               COUNT(DISTINCT substr(b.cand, 1, 7)) AS active_months,
               COUNT(DISTINCT b.id) AS receipts,
               ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
               ROUND(SUM(v.profit), 2) AS profit,
               SUM(CASE WHEN v.cantitate < 0 THEN -v.cantitate ELSE 0 END) AS ret_u,
               SUM(CASE WHEN v.cantitate > 0 THEN v.cantitate ELSE 0 END) AS sold_u
        FROM bonuri b
        JOIN vanzari v ON v.id_bon = b.id
        JOIN magazine m ON m.id = b.id_magazin
        {joins_sql}
        WHERE {where_sql}
        GROUP BY b.id_magazin
        """,
        params,
    )
    sales_by_store = {int(r["id_magazin"]): r for r in sales_rows}

    # Detect store-month outage anomalies dynamically
    outage_rows = query_all(
        conn,
        f"""
        WITH sm AS (
            SELECT b.id_magazin, substr(b.cand, 1, 7) AS luna,
                   SUM(v.valoare_fara_tva) AS rev
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            JOIN magazine m ON m.id = b.id_magazin
            {joins_sql}
            WHERE {where_sql}
            GROUP BY b.id_magazin, substr(b.cand, 1, 7)
        ),
        sm_lag AS (
            SELECT id_magazin, luna, rev,
                   LAG(rev) OVER (PARTITION BY id_magazin ORDER BY luna) AS prev_rev
            FROM sm
        )
        SELECT DISTINCT id_magazin
        FROM sm_lag
        WHERE prev_rev > 0 AND (rev - prev_rev) / prev_rev < -0.50
        """,
        params,
    )
    outage_store_ids = {int(r["id_magazin"]) for r in outage_rows}

    targets = compute_targets(conn, filters)
    target_available = targets["target_available"]
    tgt_by_store = targets["by_store"]

    meta_clauses: list[str] = []
    meta_params: list[int] = []
    if filters.region_id is not None:
        meta_clauses.append("m.id_regiune = ?")
        meta_params.append(filters.region_id)
    if filters.store_id is not None:
        meta_clauses.append("m.id = ?")
        meta_params.append(filters.store_id)
    meta_where = ("WHERE " + " AND ".join(meta_clauses)) if meta_clauses else ""

    store_meta = query_all(
        conn,
        f"""
        SELECT m.id, m.nume, m.oras, m.id_regiune, r.nume AS regiune,
               m.metri_patrati, m.nr_angajati, m.deschis_la, m.inchis_la
        FROM magazine m
        JOIN regiuni r ON r.id = m.id_regiune
        {meta_where}
        ORDER BY m.id
        """,
        tuple(meta_params),
    )

    stores: list[StorePerformance] = []
    reg_acc: dict[int, dict[str, float | int | str]] = {}

    for m in store_meta:
        sid = int(m["id"])
        rid = int(m["id_regiune"])
        s = sales_by_store.get(sid)
        rev = float(s["rev"]) if s else 0.0
        prof = float(s["profit"]) if s else 0.0
        rec = int(s["receipts"]) if s else 0
        act_mo = int(s["active_months"]) if s else 0
        sold_u = int(s["sold_u"]) if s else 0
        ret_u = int(s["ret_u"]) if s else 0

        tgt = tgt_by_store.get(sid) if target_available else None
        att = round(100.0 * rev / tgt, 2) if tgt and tgt > 0 else None
        var = round(rev - tgt, 2) if tgt is not None else None
        sqm = int(m["metri_patrati"])
        emp = int(m["nr_angajati"])
        status = _store_status(m["deschis_la"], m["inchis_la"])

        flags: list[str] = []
        if status == "closed":
            flags.append("closed")
        elif status == "opened_mid_period":
            flags.append("opened_mid_period")
        if att is not None and att < 82.0:
            flags.append("sustained_underperformance")
        if sid in outage_store_ids:
            flags.append("outage_month")

        stores.append(
            StorePerformance(
                id=sid,
                nume=m["nume"],
                regiune=m["regiune"],
                oras=m["oras"],
                sqm=sqm,
                employees=emp,
                deschis_la=m["deschis_la"],
                inchis_la=m["inchis_la"],
                status=status,
                active_months=act_mo,
                revenue_ron=rev,
                target_ron=tgt,
                attainment_pct=att,
                variance_ron=var,
                rev_per_active_month=round(rev / act_mo, 2) if act_mo > 0 else 0.0,
                rev_per_sqm_month=round(rev / (sqm * act_mo), 2)
                if act_mo > 0 and sqm > 0
                else 0.0,
                rev_per_emp_month=round(rev / (emp * act_mo), 2)
                if act_mo > 0 and emp > 0
                else 0.0,
                profit_ron=prof,
                margin_pct=round(100.0 * prof / rev, 2) if rev > 0 else 0.0,
                receipts=rec,
                aov_ron=round(rev / rec, 2) if rec > 0 else 0.0,
                return_rate_pct=round(100.0 * ret_u / sold_u, 2) if sold_u > 0 else 0.0,
                anomaly_flags=flags,
            )
        )

        acc = reg_acc.setdefault(
            rid,
            {
                "id": rid,
                "nume": m["regiune"],
                "store_count": 0,
                "open_stores": 0,
                "rev": 0.0,
                "profit": 0.0,
                "tgt": 0.0,
            },
        )
        acc["store_count"] = int(acc["store_count"]) + 1
        if m["inchis_la"] is None:
            acc["open_stores"] = int(acc["open_stores"]) + 1
        acc["rev"] = float(acc["rev"]) + rev
        acc["profit"] = float(acc["profit"]) + prof
        if tgt is not None:
            acc["tgt"] = float(acc["tgt"]) + tgt

    regions: list[RegionPerformance] = []
    for rid, acc in reg_acc.items():
        r_rev = round(float(acc["rev"]), 2)
        r_prof = round(float(acc["profit"]), 2)
        r_tgt = round(float(acc["tgt"]), 2) if target_available else None
        r_att = (
            round(100.0 * r_rev / r_tgt, 2)
            if target_available and r_tgt and r_tgt > 0
            else None
        )
        r_var = (
            round(r_rev - r_tgt, 2)
            if target_available and r_tgt is not None
            else None
        )
        regions.append(
            RegionPerformance(
                id=rid,
                nume=str(acc["nume"]),
                store_count=int(acc["store_count"]),
                open_stores=int(acc["open_stores"]),
                revenue_ron=r_rev,
                target_ron=r_tgt,
                attainment_pct=r_att,
                variance_ron=r_var,
                margin_pct=round(100.0 * r_prof / r_rev, 2) if r_rev > 0 else 0.0,
            )
        )
    regions.sort(
        key=lambda r: (r.attainment_pct if r.attainment_pct is not None else 999.0, -r.revenue_ron)
    )

    if sort_by == "attainment_pct":
        stores.sort(
            key=lambda s: (s.attainment_pct if s.attainment_pct is not None else 999.0, -s.revenue_ron)
        )
    else:
        stores.sort(key=lambda s: getattr(s, sort_by), reverse=True)

    chain_avg = None
    chain_excl = None
    if target_available:
        tot_rev = sum(s.revenue_ron for s in stores)
        tot_tgt = sum(s.target_ron or 0.0 for s in stores)
        if tot_tgt > 0:
            chain_avg = round(100.0 * tot_rev / tot_tgt, 2)
        non_outliers = [
            s for s in stores if s.attainment_pct is None or s.attainment_pct >= 80.0
        ]
        excl_rev = sum(s.revenue_ron for s in non_outliers)
        excl_tgt = sum(s.target_ron or 0.0 for s in non_outliers)
        if excl_tgt > 0:
            chain_excl = round(100.0 * excl_rev / excl_tgt, 2)

    return StoresResponse(
        currency=settings.currency_label,
        target_available=target_available,
        regions=regions,
        stores=stores,
        chain_avg_attainment_pct=chain_avg,
        chain_avg_excl_outliers_pct=chain_excl,
    )


def _fetch_store_series(
    conn: sqlite3.Connection,
    store_id: int,
    filters: GlobalFilters,
    granularity: Literal["month", "week"],
) -> list[StoreTrendPoint]:
    scoped = GlobalFilters(
        start_date=filters.start_date,
        end_date=filters.end_date,
        region_id=None,
        store_id=store_id,
        category_id=filters.category_id,
        subcategory_id=filters.subcategory_id,
    )
    where_sql, params, needs_mag, needs_prod, needs_cat = build_sales_where(scoped)
    joins_sql = sales_joins_sql(needs_mag, needs_prod, needs_cat)
    period_expr = (
        "substr(b.cand, 1, 7)" if granularity == "month" else "strftime('%Y-W%W', b.cand)"
    )

    rows = query_all(
        conn,
        f"""
        SELECT {period_expr} AS period,
               ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
               COUNT(DISTINCT b.id) AS receipts
        FROM bonuri b
        JOIN vanzari v ON v.id_bon = b.id
        {joins_sql}
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY 1
        """,
        params,
    )

    rec_period = (
        "substr(data, 1, 7)" if granularity == "month" else "strftime('%Y-W%W', data)"
    )
    deliv_rows = query_all(
        conn,
        f"""
        SELECT {rec_period} AS period, SUM(cantitate) AS qty
        FROM receptii
        WHERE id_magazin = ? AND tip = 'livrare' AND data BETWEEN ? AND ?
        GROUP BY 1
        """,
        (store_id, filters.start_date, filters.end_date),
    )
    deliv_map = {r["period"]: int(r["qty"]) for r in deliv_rows}

    targets = compute_targets(conn, scoped)
    tgt_map = targets["by_month"] if granularity == "month" and targets["target_available"] else {}

    out: list[StoreTrendPoint] = []
    for r in rows:
        p = r["period"]
        rev = float(r["rev"])
        tgt = tgt_map.get(p)
        att = round(100.0 * rev / tgt, 2) if tgt and tgt > 0 else None
        out.append(
            StoreTrendPoint(
                period=p,
                revenue_ron=rev,
                target_ron=tgt,
                attainment_pct=att,
                receipts=int(r["receipts"]),
                delivery_qty=deliv_map.get(p, 0),
            )
        )
    return out


@router.get("/stores/{store_id}/trend", response_model=StoreTrendResponse)
def get_store_trend(
    store_id: int,
    granularity: Literal["month", "week"] = Query(default="month"),
    filters: GlobalFilters = Depends(get_store_trend_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> StoreTrendResponse:
    exists = query_one(conn, "SELECT id, oras, deschis_la, inchis_la FROM magazine WHERE id = ?", (store_id,))
    if not exists:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found.")

    single_filters = GlobalFilters(
        start_date=filters.start_date,
        end_date=filters.end_date,
        region_id=None,
        store_id=store_id,
        category_id=filters.category_id,
        subcategory_id=filters.subcategory_id,
    )
    store_perf = get_stores(sort_by="attainment_pct", filters=single_filters, conn=conn).stores[0]
    series = _fetch_store_series(conn, store_id, filters, granularity)

    # Sibling comparison in same city if available
    sibling = query_one(
        conn,
        "SELECT id, nume FROM magazine WHERE oras = ? AND id != ? ORDER BY id LIMIT 1",
        (exists["oras"], store_id),
    )
    sibling_comp = (
        SiblingComparison(
            store_id=int(sibling["id"]),
            store_name=sibling["nume"],
            series=_fetch_store_series(conn, int(sibling["id"]), filters, granularity),
        )
        if sibling
        else None
    )

    # Dynamically detect operational events (outages, sustained step-down, open/close)
    events: list[StoreEvent] = []
    if filters.start_date <= exists["deschis_la"] <= filters.end_date:
        events.append(
            StoreEvent(
                date=exists["deschis_la"],
                title="Store Opened",
                impact_summary=f"Opened on {exists['deschis_la']}; ramped across {store_perf.active_months} active months.",
            )
        )
    if exists["inchis_la"] and filters.start_date <= exists["inchis_la"] <= filters.end_date:
        events.append(
            StoreEvent(
                date=exists["inchis_la"],
                title="Store Permanently Closed",
                impact_summary=f"Closed on {exists['inchis_la']}; remaining stock transferred out.",
            )
        )

    # Outage gaps (>= 4 consecutive days with 0 receipts inside selected window)
    day_rows = query_all(
        conn,
        """
        SELECT DISTINCT substr(cand, 1, 10) AS d
        FROM bonuri
        WHERE id_magazin = ? AND cand >= ? AND cand < ?
        ORDER BY 1
        """,
        (store_id, filters.start_ts, filters.end_ts_excl),
    )
    days = [date.fromisoformat(r["d"]) for r in day_rows]
    for idx in range(1, len(days)):
        gap_days = (days[idx] - days[idx - 1]).days - 1
        if gap_days >= 4:
            events.append(
                StoreEvent(
                    date=days[idx - 1].isoformat(),
                    title=f"{gap_days}-Day Operating Outage",
                    impact_summary=f"Zero receipts recorded from {days[idx - 1]} to {days[idx]} ({gap_days} closed days).",
                )
            )

    # Sustained attainment step-down detection on monthly series
    if granularity == "month" and len(series) >= 6:
        for idx in range(2, len(series) - 2):
            prev_att = [p.attainment_pct for p in series[:idx] if p.attainment_pct is not None]
            next_att = [p.attainment_pct for p in series[idx:] if p.attainment_pct is not None]
            if prev_att and next_att:
                avg_before = sum(prev_att) / len(prev_att)
                avg_after = sum(next_att) / len(next_att)
                if avg_before >= 90.0 and avg_after < 75.0 and (avg_before - avg_after) >= 20.0:
                    events.append(
                        StoreEvent(
                            date=series[idx].period,
                            title="Sustained Revenue Step-Down",
                            impact_summary=f"Attainment shifted from {avg_before:.1f}% avg before {series[idx].period} to {avg_after:.1f}% after.",
                        )
                    )
                    break

    # Transfer records (if any)
    transfers: list[StoreTransferSummary] = []
    tr_rows = query_all(
        conn,
        """
        SELECT r.data, r.id_magazin, m.nume, COUNT(*) AS skus, SUM(r.cantitate) AS units
        FROM receptii r
        JOIN magazine m ON m.id = r.id_magazin
        WHERE r.tip = 'transfer'
          AND r.data IN (SELECT DISTINCT data FROM receptii WHERE id_magazin = ? AND tip = 'transfer')
        GROUP BY r.data, r.id_magazin
        ORDER BY units ASC
        """,
        (store_id,),
    )
    for r in tr_rows:
        transfers.append(
            StoreTransferSummary(
                store_id=int(r["id_magazin"]),
                store_name=r["nume"],
                skus=int(r["skus"]),
                units=int(r["units"]),
            )
        )

    return StoreTrendResponse(
        currency=settings.currency_label,
        granularity=granularity,
        store=store_perf,
        series=series,
        sibling_comparison=sibling_comp,
        events=events,
        transfers=transfers,
    )
