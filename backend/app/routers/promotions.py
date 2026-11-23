"""Promotions & Margin Lab endpoints."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends

from ..config import settings
from ..db import get_db, query_all, query_one
from ..schemas import (
    CampaignPerformance,
    ExcludedTestPromo,
    PromotionsResponse,
    PromotionsSummary,
    YoYCampaignComparison,
)
from ..services.filters import (
    TEST_PROMO_EXCLUDE_SQL,
    GlobalFilters,
    build_sales_where,
    get_global_filters,
    sales_joins_sql,
)

router = APIRouter(tags=["promotions"])


def _verdict(
    profit_ron: float, margin_pct: float, profit_uplift_pct: float
) -> Literal["profitable", "margin_eroding", "net_loss"]:
    if profit_ron < 0:
        return "net_loss"
    if profit_uplift_pct < 0 or margin_pct < 15.0:
        return "margin_eroding"
    return "profitable"


@router.get("/promotions", response_model=PromotionsResponse)
def get_promotions(
    filters: GlobalFilters = Depends(get_global_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> PromotionsResponse:
    where_sql, params, needs_mag, needs_prod, needs_cat = build_sales_where(filters)
    joins_sql = sales_joins_sql(needs_mag, needs_prod, needs_cat)

    # Filtered total net revenue for promo revenue share %
    tot_row = query_one(
        conn,
        f"""
        SELECT ROUND(COALESCE(SUM(v.valoare_fara_tva), 0), 2) AS total_rev
        FROM bonuri b
        JOIN vanzari v ON v.id_bon = b.id
        {joins_sql}
        WHERE {where_sql}
        """,
        params,
    )
    total_filtered_rev = float(tot_row["total_rev"]) if tot_row else 0.0

    # Excluded test/empty promos (surfaced transparently for data hygiene)
    test_rows = query_all(
        conn,
        """
        SELECT o.id, o.nume, o.tip, o.valoare, o.inceput, o.sfarsit,
               (SELECT COUNT(*) FROM oferte_produse op WHERE op.id_oferta = o.id) AS sku_cnt
        FROM oferte o
        WHERE NOT ("""
        + TEST_PROMO_EXCLUDE_SQL
        + """)
        ORDER BY o.inceput, o.id
        """,
    )
    excluded_test_promos = [
        ExcludedTestPromo(
            id=int(r["id"]),
            nume=r["nume"],
            tip=r["tip"],
            valoare=float(r["valoare"]),
            inceput=r["inceput"],
            sfarsit=r["sfarsit"],
            reason="Test record / 0 linked SKUs" if r["sku_cnt"] == 0 else "Test campaign name",
        )
        for r in test_rows
    ]

    # Direct campaign performance (filtered by global filters, strictly cantitate > 0 for below-cost count)
    direct_rows = query_all(
        conn,
        f"""
        SELECT o.id, o.nume, o.tip, o.valoare, o.inceput, o.sfarsit,
               CAST(julianday(o.sfarsit) - julianday(o.inceput) + 1 AS INT) AS days,
               (SELECT COUNT(*) FROM oferte_produse op WHERE op.id_oferta = o.id) AS sku_count,
               ROUND(COALESCE(SUM(v.valoare_fara_tva), 0), 2) AS rev,
               ROUND(COALESCE(SUM(v.reducere), 0), 2) AS disc,
               ROUND(COALESCE(SUM(v.profit), 0), 2) AS profit,
               COALESCE(SUM(v.cantitate), 0) AS units_net,
               COALESCE(SUM(CASE WHEN v.cantitate > 0 AND v.profit < 0 THEN 1 ELSE 0 END), 0) AS below_cost_lines,
               ROUND(COALESCE(SUM(CASE WHEN v.cantitate > 0 AND v.profit < 0 THEN v.profit ELSE 0 END), 0), 2) AS below_cost_loss
        FROM oferte o
        LEFT JOIN vanzari v ON v.id_oferta = o.id
        LEFT JOIN bonuri b ON b.id = v.id_bon
        {"LEFT JOIN magazine m ON m.id = b.id_magazin" if needs_mag else ""}
        {"LEFT JOIN produse p ON p.id = v.id_produs" if (needs_prod or needs_cat) else ""}
        {"LEFT JOIN categorii c ON c.id = p.id_categorie" if needs_cat else ""}
        WHERE {TEST_PROMO_EXCLUDE_SQL}
          AND o.sfarsit >= :start_date AND o.inceput <= :end_date
          AND (v.id IS NULL OR ({where_sql}))
        GROUP BY o.id
        ORDER BY o.inceput, o.id
        """,
        {**params, "start_date": filters.start_date, "end_date": filters.end_date},
    )

    # Pre-vs-During 28d uplift per campaign (respecting store/region/category filters, independent of date range)
    nd_where, nd_params, nd_mag, nd_prod, nd_cat = build_sales_where(
        filters, include_dates=False
    )
    nd_joins = sales_joins_sql(nd_mag, nd_prod, nd_cat)
    uplift_rows = query_all(
        conn,
        f"""
        SELECT o.id,
               CAST(julianday(o.sfarsit) - julianday(o.inceput) + 1 AS INT) AS days,
               ROUND(COALESCE(SUM(CASE WHEN b.cand >= o.inceput || ' 00:00:00'
                                        AND b.cand < date(o.sfarsit, '+1 day') || ' 00:00:00'
                                       THEN v.valoare_fara_tva ELSE 0 END), 0), 2) AS rev_dur,
               ROUND(COALESCE(SUM(CASE WHEN b.cand >= o.inceput || ' 00:00:00'
                                        AND b.cand < date(o.sfarsit, '+1 day') || ' 00:00:00'
                                       THEN v.profit ELSE 0 END), 0), 2) AS prof_dur,
               ROUND(COALESCE(SUM(CASE WHEN b.cand >= date(o.inceput, '-28 days') || ' 00:00:00'
                                        AND b.cand < o.inceput || ' 00:00:00'
                                       THEN v.valoare_fara_tva ELSE 0 END), 0), 2) AS rev_pre,
               ROUND(COALESCE(SUM(CASE WHEN b.cand >= date(o.inceput, '-28 days') || ' 00:00:00'
                                        AND b.cand < o.inceput || ' 00:00:00'
                                       THEN v.profit ELSE 0 END), 0), 2) AS prof_pre
        FROM oferte o
        JOIN oferte_produse op ON op.id_oferta = o.id
        JOIN vanzari v ON v.id_produs = op.id_produs
        JOIN bonuri b ON b.id = v.id_bon
        {nd_joins}
        WHERE {TEST_PROMO_EXCLUDE_SQL}
          AND o.sfarsit >= :start_date AND o.inceput <= :end_date
          AND b.cand >= date(o.inceput, '-28 days') || ' 00:00:00'
          AND b.cand < date(o.sfarsit, '+1 day') || ' 00:00:00'
          AND ({nd_where})
        GROUP BY o.id
        """,
        {**nd_params, "start_date": filters.start_date, "end_date": filters.end_date},
    )
    uplift_map = {int(r["id"]): r for r in uplift_rows}

    campaigns: list[CampaignPerformance] = []
    for r in direct_rows:
        cid = int(r["id"])
        days = max(int(r["days"]), 1)
        rev = float(r["rev"])
        disc = float(r["disc"])
        prof = float(r["profit"])
        mgn = round(100.0 * prof / rev, 2) if rev > 0 else 0.0

        u = uplift_map.get(cid)
        rev_d = round(float(u["rev_dur"]) / days, 2) if u else 0.0
        rev_p = round(float(u["rev_pre"]) / 28.0, 2) if u else 0.0
        prof_d = round(float(u["prof_dur"]) / days, 2) if u else 0.0
        prof_p = round(float(u["prof_pre"]) / 28.0, 2) if u else 0.0
        rev_up = round(100.0 * (rev_d - rev_p) / rev_p, 2) if rev_p > 0 else 0.0
        prof_up = round(100.0 * (prof_d - prof_p) / prof_p, 2) if prof_p > 0 else 0.0

        campaigns.append(
            CampaignPerformance(
                id=cid,
                nume=r["nume"],
                tip=r["tip"],
                valoare=float(r["valoare"]),
                inceput=r["inceput"],
                sfarsit=r["sfarsit"],
                days=days,
                sku_count=int(r["sku_count"]),
                revenue_ron=rev,
                discount_ron=disc,
                profit_ron=prof,
                margin_pct=mgn,
                units_net=int(r["units_net"]),
                below_cost_lines=int(r["below_cost_lines"]),
                below_cost_loss_ron=float(r["below_cost_loss"]),
                rev_per_day_during=rev_d,
                rev_per_day_pre28=rev_p,
                rev_uplift_pct=rev_up,
                profit_per_day_during=prof_d,
                profit_per_day_pre28=prof_p,
                profit_uplift_pct=prof_up,
                verdict=_verdict(prof, mgn, prof_up),
            )
        )

    # YoY SKU-matched comparison (e.g. Vara în siguranță -15% 2025 vs -20% 2026)
    sku_sets: dict[int, set[int]] = {}
    for row in query_all(conn, "SELECT id_oferta, id_produs FROM oferte_produse"):
        sku_sets.setdefault(int(row["id_oferta"]), set()).add(int(row["id_produs"]))

    camp_by_id = {c.id: c for c in campaigns}
    yoy_comparisons: list[YoYCampaignComparison] = []
    camp_ids = [c.id for c in campaigns]
    for i in range(len(camp_ids)):
        for j in range(i + 1, len(camp_ids)):
            c1, c2 = camp_by_id[camp_ids[i]], camp_by_id[camp_ids[j]]
            if c1.inceput[:4] == c2.inceput[:4]:
                continue
            s1, s2 = sku_sets.get(c1.id, set()), sku_sets.get(c2.id, set())
            if not s1 or not s2:
                continue
            overlap = len(s1 & s2) / max(len(s1), len(s2))
            if overlap >= 0.8:
                older, newer = (c1, c2) if c1.inceput < c2.inceput else (c2, c1)
                yoy_comparisons.append(
                    YoYCampaignComparison(
                        label=f"{older.nume} vs. {newer.nume}",
                        campaign_2025=older,
                        campaign_2026=newer,
                        rev_delta_ron=round(newer.revenue_ron - older.revenue_ron, 2),
                        disc_delta_ron=round(newer.discount_ron - older.discount_ron, 2),
                        profit_delta_ron=round(newer.profit_ron - older.profit_ron, 2),
                        margin_delta_pp=round(newer.margin_pct - older.margin_pct, 2),
                    )
                )

    promo_rev = round(sum(c.revenue_ron for c in campaigns), 2)
    promo_disc = round(sum(c.discount_ron for c in campaigns), 2)
    promo_prof = round(sum(c.profit_ron for c in campaigns), 2)
    summary = PromotionsSummary(
        active_campaigns=len(campaigns),
        promo_revenue_ron=promo_rev,
        promo_rev_share_pct=round(100.0 * promo_rev / total_filtered_rev, 2)
        if total_filtered_rev > 0
        else 0.0,
        total_discount_ron=promo_disc,
        promo_profit_ron=promo_prof,
        promo_margin_pct=round(100.0 * promo_prof / promo_rev, 2) if promo_rev > 0 else 0.0,
        below_cost_lines=sum(c.below_cost_lines for c in campaigns),
        below_cost_loss_ron=round(sum(c.below_cost_loss_ron for c in campaigns), 2),
    )

    return PromotionsResponse(
        currency=settings.currency_label,
        summary=summary,
        campaigns=campaigns,
        yoy_comparisons=yoy_comparisons,
        excluded_test_promos=excluded_test_promos,
    )
