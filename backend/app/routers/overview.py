"""Health, filter metadata, and Executive Overview endpoints."""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query

from ..config import settings
from ..db import get_db, query_all, query_one
from ..schemas import (
    CategoryMixItem,
    CategoryOption,
    FiltersResponse,
    HealthResponse,
    OverviewAnnotation,
    OverviewKpis,
    OverviewResponse,
    OverviewSeriesPoint,
    PriceWaveSummary,
    ProductSummaryItem,
    RegionOption,
    StoreOption,
    SubcategoryOption,
)
from ..services.cache import cached_call, make_cache_key
from ..services.filters import (
    GlobalFilters,
    build_sales_where,
    compute_targets,
    get_global_filters,
    sales_joins_sql,
)

router = APIRouter(tags=["overview"])


def _store_status(deschis_la: str, inchis_la: str | None) -> Literal["active", "opened_mid_period", "closed"]:
    if inchis_la is not None:
        return "closed"
    if deschis_la > settings.default_start_date:
        return "opened_mid_period"
    return "active"


@router.get("/health", response_model=HealthResponse)
def health(conn: sqlite3.Connection = Depends(get_db)) -> HealthResponse:
    row = query_one(
        conn,
        """
        SELECT (SELECT substr(cand, 1, 10) FROM bonuri ORDER BY cand ASC LIMIT 1) AS d_min,
               (SELECT substr(cand, 1, 10) FROM bonuri ORDER BY cand DESC LIMIT 1) AS d_max,
               (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%') AS tables_cnt
        """,
    )
    return HealthResponse(
        status="ok",
        db_mode="ro",
        currency=settings.currency_label,
        date_min=row["d_min"],
        date_max=row["d_max"],
        tables_verified=int(row["tables_cnt"]),
    )


@router.get("/filters", response_model=FiltersResponse)
def get_filters(conn: sqlite3.Connection = Depends(get_db)) -> FiltersResponse:
    def _compute() -> FiltersResponse:
        bounds = query_one(
            conn,
            """
            SELECT (SELECT substr(cand, 1, 10) FROM bonuri ORDER BY cand ASC LIMIT 1) AS d_min,
                   (SELECT substr(cand, 1, 10) FROM bonuri ORDER BY cand DESC LIMIT 1) AS d_max
            """,
        )
        regions = [
            RegionOption(id=r["id"], nume=r["nume"])
            for r in query_all(conn, "SELECT id, nume FROM regiuni ORDER BY nume")
        ]
        stores = [
            StoreOption(
                id=r["id"],
                nume=r["nume"],
                oras=r["oras"],
                id_regiune=r["id_regiune"],
                deschis_la=r["deschis_la"],
                inchis_la=r["inchis_la"],
                status=_store_status(r["deschis_la"], r["inchis_la"]),
            )
            for r in query_all(
                conn,
                "SELECT id, nume, oras, id_regiune, deschis_la, inchis_la FROM magazine ORDER BY nume",
            )
        ]

        cat_rows = query_all(conn, "SELECT id, nume, id_parinte FROM categorii ORDER BY id")
        l1_map: dict[int, CategoryOption] = {}
        for r in cat_rows:
            if r["id_parinte"] is None:
                l1_map[r["id"]] = CategoryOption(id=r["id"], nume=r["nume"], subcategories=[])
        for r in cat_rows:
            parent_id = r["id_parinte"]
            if parent_id is not None and parent_id in l1_map:
                l1_map[parent_id].subcategories.append(
                    SubcategoryOption(id=r["id"], nume=r["nume"])
                )

        return FiltersResponse(
            date_min=bounds["d_min"],
            date_max=bounds["d_max"],
            currency=settings.currency_label,
            regions=regions,
            stores=stores,
            categories=sorted(l1_map.values(), key=lambda c: c.nume),
        )

    return cached_call(make_cache_key("filters"), _compute)


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    granularity: Literal["month", "week"] = Query(default="month"),
    filters: GlobalFilters = Depends(get_global_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> OverviewResponse:
    def _compute() -> OverviewResponse:
        return _compute_overview(granularity, filters, conn)

    return cached_call(make_cache_key("overview", filters, granularity=granularity), _compute)


def _compute_overview(
    granularity: Literal["month", "week"],
    filters: GlobalFilters,
    conn: sqlite3.Connection,
) -> OverviewResponse:
    where_sql, params, needs_mag, needs_prod, needs_cat = build_sales_where(filters)
    joins_sql = sales_joins_sql(needs_mag, needs_prod, needs_cat)

    # Time series + headline totals in a single scan (each bonuri.id belongs to exactly 1 month/week)
    period_expr = (
        "substr(b.cand, 1, 7)" if granularity == "month" else "strftime('%Y-W%W', b.cand)"
    )
    series_rows = query_all(
        conn,
        f"""
        SELECT {period_expr} AS period,
               ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
               ROUND(SUM(CASE WHEN v.cantitate > 0 THEN v.valoare_fara_tva ELSE 0 END), 2) AS gross_rev,
               ROUND(SUM(v.profit), 2) AS profit,
               ROUND(SUM(v.reducere), 2) AS disc,
               SUM(v.cantitate) AS units_net,
               COUNT(DISTINCT b.id) AS receipts,
               SUM(CASE WHEN v.cantitate < 0 THEN 1 ELSE 0 END) AS ret_lines,
               ROUND(ABS(SUM(CASE WHEN v.cantitate < 0 THEN v.valoare_fara_tva ELSE 0 END)), 2) AS ret_val,
               SUM(CASE WHEN v.cantitate < 0 THEN -v.cantitate ELSE 0 END) AS ret_units,
               SUM(CASE WHEN v.cantitate > 0 THEN v.cantitate ELSE 0 END) AS sold_units
        FROM bonuri b
        JOIN vanzari v ON v.id_bon = b.id
        {joins_sql}
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY 1
        """,
        params,
    )

    net_rev = round(sum(float(r["rev"]) for r in series_rows), 2)
    gross_rev = round(sum(float(r["gross_rev"]) for r in series_rows), 2)
    profit = round(sum(float(r["profit"]) for r in series_rows), 2)
    disc = round(sum(float(r["disc"]) for r in series_rows), 2)
    units_net = sum(int(r["units_net"]) for r in series_rows)
    receipts = sum(int(r["receipts"]) for r in series_rows)
    ret_lines = sum(int(r["ret_lines"]) for r in series_rows)
    ret_val = round(sum(float(r["ret_val"]) for r in series_rows), 2)
    ret_units = sum(int(r["ret_units"]) for r in series_rows)
    sold_units = sum(int(r["sold_units"]) for r in series_rows)

    targets = compute_targets(conn, filters)
    target_available = targets["target_available"]
    target_ron = targets["total_target_ron"]
    attainment_pct = (
        round(100.0 * net_rev / target_ron, 2)
        if target_available and target_ron and target_ron > 0
        else None
    )
    variance_ron = (
        round(net_rev - target_ron, 2)
        if target_available and target_ron is not None
        else None
    )

    # Previous period comparison (skip scan if window starts at dataset start)
    rev_vs_prev_pct = None
    if filters.start_date > settings.default_start_date:
        span_days = (filters.end_dt - filters.start_dt).days + 1
        prev_end_dt = filters.start_dt - timedelta(days=1)
        prev_start_dt = prev_end_dt - timedelta(days=span_days - 1)
        prev_filters = GlobalFilters(
            start_date=prev_start_dt.isoformat(),
            end_date=prev_end_dt.isoformat(),
            region_id=filters.region_id,
            store_id=filters.store_id,
            category_id=filters.category_id,
            subcategory_id=filters.subcategory_id,
        )
        p_where, p_params, p_mag, p_prod, p_cat = build_sales_where(prev_filters)
        p_joins = sales_joins_sql(p_mag, p_prod, p_cat)
        prev_row = query_one(
            conn,
            f"""
            SELECT ROUND(COALESCE(SUM(v.valoare_fara_tva), 0), 2) AS prev_rev
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            {p_joins}
            WHERE {p_where}
            """,
            p_params,
        )
        prev_rev = float(prev_row["prev_rev"]) if prev_row else 0.0
        if prev_rev > 0:
            rev_vs_prev_pct = round(100.0 * (net_rev - prev_rev) / prev_rev, 2)

    kpis = OverviewKpis(
        net_revenue_ron=net_rev,
        gross_revenue_ron=gross_rev,
        gross_profit_ron=profit,
        margin_pct=round(100.0 * profit / net_rev, 2) if net_rev else 0.0,
        discount_ron=disc,
        units_net=units_net,
        receipts=receipts,
        aov_ron=round(net_rev / receipts, 2) if receipts else 0.0,
        target_ron=target_ron,
        attainment_pct=attainment_pct,
        variance_ron=variance_ron,
        target_available=target_available,
        return_lines=ret_lines,
        return_value_ron=ret_val,
        return_rate_units_pct=round(100.0 * ret_units / sold_units, 2) if sold_units else 0.0,
        rev_vs_prev_period_pct=rev_vs_prev_pct,
    )

    by_month_targets = targets["by_month"]
    series: list[OverviewSeriesPoint] = []
    for r in series_rows:
        period = r["period"]
        rev = float(r["rev"])
        prof = float(r["profit"])
        rec = int(r["receipts"])
        tgt = (
            by_month_targets.get(period)
            if granularity == "month" and target_available
            else None
        )
        att = round(100.0 * rev / tgt, 2) if tgt and tgt > 0 else None
        series.append(
            OverviewSeriesPoint(
                period=period,
                revenue_ron=rev,
                target_ron=tgt,
                attainment_pct=att,
                profit_ron=prof,
                margin_pct=round(100.0 * prof / rev, 2) if rev else 0.0,
                receipts=rec,
                aov_ron=round(rev / rec, 2) if rec else 0.0,
            )
        )

    # Dynamic price wave detection (month with largest repricing wave)
    wave_row = query_one(
        conn,
        """
        WITH pc AS (
            SELECT p1.id_produs, substr(p2.de_la, 1, 7) AS luna,
                   100.0 * (p2.pret_fara_tva - p1.pret_fara_tva) / p1.pret_fara_tva AS pr_chg,
                   100.0 * (p2.cost_achizitie - p1.cost_achizitie) / p1.cost_achizitie AS c_chg
            FROM preturi p1
            JOIN preturi p2 ON p2.id_produs = p1.id_produs AND p2.de_la = date(p1.pana_la, '+1 day')
        )
        SELECT luna, COUNT(*) AS n,
               ROUND(AVG(pr_chg), 2) AS avg_pr,
               ROUND(AVG(c_chg), 2) AS avg_c,
               (SELECT COUNT(*) FROM produse) AS total_skus
        FROM pc
        GROUP BY luna
        ORDER BY n DESC
        LIMIT 1
        """,
    )
    price_wave = (
        PriceWaveSummary(
            month=wave_row["luna"],
            repriced_skus=int(wave_row["n"]),
            total_skus=int(wave_row["total_skus"]),
            avg_price_chg_pct=float(wave_row["avg_pr"]),
            avg_cost_chg_pct=float(wave_row["avg_c"]),
        )
        if wave_row
        else None
    )

    annotations: list[OverviewAnnotation] = []
    if price_wave and filters.start_date[:7] <= price_wave.month <= filters.end_date[:7]:
        annotations.append(
            OverviewAnnotation(
                period=price_wave.month,
                label=f"Repricing Wave ({price_wave.repriced_skus} SKUs)",
                detail=f"{price_wave.repriced_skus}/{price_wave.total_skus} SKUs repriced (+{price_wave.avg_price_chg_pct:.1f}% price vs +{price_wave.avg_cost_chg_pct:.1f}% cost)",
                type="repricing",
            )
        )
    for m_row in query_all(
        conn,
        """
        SELECT id, nume, deschis_la, inchis_la FROM magazine
        WHERE (deschis_la BETWEEN ? AND ?) OR (inchis_la BETWEEN ? AND ?)
        """,
        (filters.start_date, filters.end_date, filters.start_date, filters.end_date),
    ):
        if filters.start_date <= m_row["deschis_la"] <= filters.end_date:
            annotations.append(
                OverviewAnnotation(
                    period=m_row["deschis_la"][:7],
                    label=f"Opened: {m_row['nume'].replace('Farmacia Lumen ', '')}",
                    detail=f"New store opened {m_row['deschis_la']}",
                    type="store_open",
                )
            )
        if m_row["inchis_la"] and filters.start_date <= m_row["inchis_la"] <= filters.end_date:
            annotations.append(
                OverviewAnnotation(
                    period=m_row["inchis_la"][:7],
                    label=f"Closed: {m_row['nume'].replace('Farmacia Lumen ', '')}",
                    detail=f"Store closed {m_row['inchis_la']} with stock transferred",
                    type="store_close",
                )
            )

    # Products & Category mix in a single scan.
    # When no date-subset/store/region filter applies, aggregate vanzari directly (skips 674k bonuri lookups).
    no_bonuri_filter = (
        filters.store_id is None
        and filters.region_id is None
        and filters.start_date <= settings.default_start_date
        and filters.end_date >= settings.default_end_date
    )
    if no_bonuri_filter:
        p_where, p_params, _, _, _ = build_sales_where(filters, include_dates=False)
        prod_rows = query_all(
            conn,
            f"""
            SELECT p.id, p.nume, p.brand, c2.nume AS category, p.activ,
                   COALESCE(c1.id, c2.id) AS l1_id,
                   COALESCE(c1.nume, c2.nume) AS l1_nume,
                   ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
                   ROUND(SUM(v.profit), 2) AS profit,
                   SUM(v.cantitate) AS units,
                   SUM(CASE WHEN v.cantitate < 0 THEN -v.cantitate ELSE 0 END) AS ret_u,
                   SUM(CASE WHEN v.cantitate > 0 THEN v.cantitate ELSE 0 END) AS sold_u
            FROM vanzari v
            JOIN produse p ON p.id = v.id_produs
            JOIN categorii c2 ON c2.id = p.id_categorie
            LEFT JOIN categorii c1 ON c1.id = c2.id_parinte
            WHERE {p_where}
            GROUP BY p.id
            ORDER BY rev DESC
            """,
            p_params,
        )
    else:
        cat_joins = sales_joins_sql(needs_mag, True, False)
        prod_rows = query_all(
            conn,
            f"""
            SELECT p.id, p.nume, p.brand, c2.nume AS category, p.activ,
                   COALESCE(c1.id, c2.id) AS l1_id,
                   COALESCE(c1.nume, c2.nume) AS l1_nume,
                   ROUND(SUM(v.valoare_fara_tva), 2) AS rev,
                   ROUND(SUM(v.profit), 2) AS profit,
                   SUM(v.cantitate) AS units,
                   SUM(CASE WHEN v.cantitate < 0 THEN -v.cantitate ELSE 0 END) AS ret_u,
                   SUM(CASE WHEN v.cantitate > 0 THEN v.cantitate ELSE 0 END) AS sold_u
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            {cat_joins}
            JOIN categorii c2 ON c2.id = p.id_categorie
            LEFT JOIN categorii c1 ON c1.id = c2.id_parinte
            WHERE {where_sql}
            GROUP BY p.id
            ORDER BY rev DESC
            """,
            params,
        )
    cat_acc: dict[tuple[int, str], dict[str, float | int]] = {}
    all_prods: list[ProductSummaryItem] = []
    for r in prod_rows:
        rev_p = float(r["rev"])
        prof_p = float(r["profit"])
        units_p = int(r["units"])
        ckey = (int(r["l1_id"]), r["l1_nume"])
        c_entry = cat_acc.setdefault(ckey, {"rev": 0.0, "profit": 0.0, "units": 0})
        c_entry["rev"] = float(c_entry["rev"]) + rev_p
        c_entry["profit"] = float(c_entry["profit"]) + prof_p
        c_entry["units"] = int(c_entry["units"]) + units_p
        all_prods.append(
            ProductSummaryItem(
                id=int(r["id"]),
                nume=r["nume"],
                brand=r["brand"],
                category=r["category"],
                activ=int(r["activ"]),
                revenue_ron=rev_p,
                profit_ron=prof_p,
                margin_pct=round(100.0 * prof_p / rev_p, 2) if rev_p else 0.0,
                units=units_p,
                return_rate_pct=round(100.0 * int(r["ret_u"]) / int(r["sold_u"]), 2)
                if r["sold_u"]
                else 0.0,
            )
        )
    category_mix = sorted(
        [
            CategoryMixItem(
                id=l1_id,
                nume=l1_nume,
                revenue_ron=round(float(vals["rev"]), 2),
                share_pct=round(100.0 * float(vals["rev"]) / net_rev, 2) if net_rev else 0.0,
                profit_ron=round(float(vals["profit"]), 2),
                margin_pct=round(100.0 * float(vals["profit"]) / float(vals["rev"]), 2)
                if vals["rev"]
                else 0.0,
                units=int(vals["units"]),
            )
            for (l1_id, l1_nume), vals in cat_acc.items()
        ],
        key=lambda c: c.revenue_ron,
        reverse=True,
    )
    top_products = all_prods[:10]
    active_prods = [p for p in all_prods if p.activ == 1]
    bottom_products = sorted(active_prods, key=lambda p: p.revenue_ron)[:10]

    return OverviewResponse(
        currency=settings.currency_label,
        granularity=granularity,
        kpis=kpis,
        series=series,
        annotations=annotations,
        category_mix=category_mix,
        top_products=top_products,
        bottom_products=bottom_products,
        price_wave=price_wave,
    )
