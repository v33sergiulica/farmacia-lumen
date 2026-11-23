"""Customer & Loyalty Insights endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from ..config import settings
from ..db import get_db, query_all, query_one
from ..schemas import (
    CustomerPenetration,
    CustomersDemographics,
    CustomersResponse,
    DemographicBucket,
    FrequencySegmentItem,
    MonthlyLoyaltyPoint,
)
from ..services.filters import (
    GlobalFilters,
    build_sales_where,
    get_global_filters,
    sales_joins_sql,
)

router = APIRouter(tags=["customers"])


@router.get("/customers", response_model=CustomersResponse)
def get_customers(
    filters: GlobalFilters = Depends(get_global_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> CustomersResponse:
    where_sql, params, needs_mag, needs_prod, needs_cat = build_sales_where(filters)
    joins_sql = sales_joins_sql(needs_mag, needs_prod, needs_cat)

    # Monthly loyalty trend + card vs no-card penetration in a single scan
    trend_rows = query_all(
        conn,
        f"""
        SELECT substr(b.cand, 1, 7) AS period,
               COUNT(DISTINCT CASE WHEN b.id_client IS NOT NULL THEN b.id END) AS card_rec,
               COUNT(DISTINCT CASE WHEN b.id_client IS NULL THEN b.id END) AS nocard_rec,
               COUNT(DISTINCT b.id) AS tot_rec,
               ROUND(COALESCE(SUM(CASE WHEN b.id_client IS NOT NULL THEN v.valoare_fara_tva ELSE 0 END), 0), 2) AS card_rev,
               ROUND(COALESCE(SUM(CASE WHEN b.id_client IS NULL THEN v.valoare_fara_tva ELSE 0 END), 0), 2) AS nocard_rev,
               ROUND(COALESCE(SUM(CASE WHEN b.id_client IS NOT NULL THEN v.profit ELSE 0 END), 0), 2) AS card_prof,
               ROUND(COALESCE(SUM(CASE WHEN b.id_client IS NULL THEN v.profit ELSE 0 END), 0), 2) AS nocard_prof
        FROM bonuri b
        JOIN vanzari v ON v.id_bon = b.id
        {joins_sql}
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY 1
        """,
        params,
    )
    c_rec = sum(int(r["card_rec"]) for r in trend_rows)
    n_rec = sum(int(r["nocard_rec"]) for r in trend_rows)
    c_rev = round(sum(float(r["card_rev"]) for r in trend_rows), 2)
    n_rev = round(sum(float(r["nocard_rev"]) for r in trend_rows), 2)
    c_prof = round(sum(float(r["card_prof"]) for r in trend_rows), 2)
    n_prof = round(sum(float(r["nocard_prof"]) for r in trend_rows), 2)
    tot_rec = c_rec + n_rec
    tot_rev = c_rev + n_rev

    penetration = CustomerPenetration(
        card_receipts=c_rec,
        nocard_receipts=n_rec,
        card_receipt_share_pct=round(100.0 * c_rec / tot_rec, 2) if tot_rec else 0.0,
        card_revenue_ron=c_rev,
        nocard_revenue_ron=n_rev,
        card_rev_share_pct=round(100.0 * c_rev / tot_rev, 2) if tot_rev else 0.0,
        card_aov_ron=round(c_rev / c_rec, 2) if c_rec else 0.0,
        nocard_aov_ron=round(n_rev / n_rec, 2) if n_rec else 0.0,
        card_margin_pct=round(100.0 * c_prof / c_rev, 2) if c_rev else 0.0,
        nocard_margin_pct=round(100.0 * n_prof / n_rev, 2) if n_rev else 0.0,
    )

    monthly_loyalty_trend = [
        MonthlyLoyaltyPoint(
            period=r["period"],
            card_share_pct=round(100.0 * r["card_rec"] / r["tot_rec"], 2) if r["tot_rec"] else 0.0,
            card_aov_ron=round(float(r["card_rev"]) / int(r["card_rec"]), 2) if r["card_rec"] else 0.0,
            nocard_aov_ron=round(float(r["nocard_rev"]) / int(r["nocard_rec"]), 2) if r["nocard_rec"] else 0.0,
        )
        for r in trend_rows
    ]

    # Client frequency segmentation (all registered clients in optional region_id scope)
    client_region_where = "WHERE c_reg.id_regiune = :region_id" if filters.region_id is not None else ""
    freq_rows = query_all(
        conn,
        f"""
        WITH filtered_spend AS (
            SELECT b.id_client,
                   COUNT(DISTINCT b.id) AS visits,
                   COALESCE(SUM(v.valoare_fara_tva), 0) AS spend
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            {joins_sql}
            WHERE b.id_client IS NOT NULL AND ({where_sql})
            GROUP BY b.id_client
        ),
        bucketed AS (
            SELECT c_reg.id,
                   COALESCE(fs.visits, 0) AS visits,
                   COALESCE(fs.spend, 0) AS spend,
                   CASE
                       WHEN COALESCE(fs.visits, 0) = 0 THEN '0 visits (Dormant)'
                       WHEN fs.visits = 1 THEN '1 visit (One-time)'
                       WHEN fs.visits BETWEEN 2 AND 5 THEN '2–5 visits'
                       WHEN fs.visits BETWEEN 6 AND 20 THEN '6–20 visits'
                       ELSE '20+ visits (VIP)'
                   END AS bucket,
                   CASE
                       WHEN COALESCE(fs.visits, 0) = 0 THEN 1
                       WHEN fs.visits = 1 THEN 2
                       WHEN fs.visits BETWEEN 2 AND 5 THEN 3
                       WHEN fs.visits BETWEEN 6 AND 20 THEN 4
                       ELSE 5
                   END AS ord
            FROM clienti c_reg
            LEFT JOIN filtered_spend fs ON fs.id_client = c_reg.id
            {client_region_where}
        )
        SELECT bucket, ord,
               COUNT(*) AS members,
               ROUND(SUM(spend), 2) AS rev
        FROM bucketed
        GROUP BY bucket, ord
        ORDER BY ord
        """,
        params,
    )
    total_members = sum(int(r["members"]) for r in freq_rows)
    dormant_members = 0
    one_time_members = 0
    frequency_segments: list[FrequencySegmentItem] = []
    for r in freq_rows:
        m_cnt = int(r["members"])
        rev = float(r["rev"])
        if r["ord"] == 1:
            dormant_members = m_cnt
        elif r["ord"] == 2:
            one_time_members = m_cnt
        frequency_segments.append(
            FrequencySegmentItem(
                bucket=r["bucket"],
                members=m_cnt,
                share_pct=round(100.0 * m_cnt / total_members, 2) if total_members else 0.0,
                revenue_ron=rev,
                avg_spend_ron=round(rev / m_cnt, 2) if m_cnt else 0.0,
            )
        )

    # Demographics (linked card transactions in filtered scope)
    ref_year_row = query_one(conn, "SELECT CAST(substr(MAX(cand), 1, 4) AS INT) AS y FROM bonuri")
    ref_year = int(ref_year_row["y"]) if ref_year_row and ref_year_row["y"] else 2026

    def _demo_query(group_expr: str, extra_join: str = "", order_clause: str = "rev DESC") -> list[DemographicBucket]:
        rows = query_all(
            conn,
            f"""
            SELECT {group_expr} AS label,
                   COUNT(DISTINCT cl.id) AS members,
                   COUNT(DISTINCT b.id) AS receipts,
                   ROUND(COALESCE(SUM(v.valoare_fara_tva), 0), 2) AS rev
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            JOIN clienti cl ON cl.id = b.id_client
            {extra_join}
            {joins_sql}
            WHERE b.id_client IS NOT NULL AND ({where_sql})
            GROUP BY 1
            ORDER BY {order_clause}
            """,
            params,
        )
        return [
            DemographicBucket(
                label=str(r["label"]),
                members=int(r["members"]),
                receipts=int(r["receipts"]),
                revenue_ron=float(r["rev"]),
                avg_spend_per_member_ron=round(float(r["rev"]) / int(r["members"]), 2)
                if r["members"]
                else 0.0,
            )
            for r in rows
        ]

    by_sex = _demo_query("cl.sex")
    by_age_band = _demo_query(
        f"""
        CASE
            WHEN ({ref_year} - cl.an_nasterii) < 25 THEN '<25'
            WHEN ({ref_year} - cl.an_nasterii) BETWEEN 25 AND 34 THEN '25–34'
            WHEN ({ref_year} - cl.an_nasterii) BETWEEN 35 AND 44 THEN '35–44'
            WHEN ({ref_year} - cl.an_nasterii) BETWEEN 45 AND 54 THEN '45–54'
            WHEN ({ref_year} - cl.an_nasterii) BETWEEN 55 AND 64 THEN '55–64'
            ELSE '65+'
        END
        """,
        order_clause="MIN(cl.an_nasterii) DESC",
    )
    by_region = _demo_query(
        "rg.nume",
        extra_join="JOIN regiuni rg ON rg.id = cl.id_regiune",
    )

    return CustomersResponse(
        currency=settings.currency_label,
        total_registered_members=total_members,
        dormant_members=dormant_members,
        one_time_members=one_time_members,
        penetration=penetration,
        frequency_segments=frequency_segments,
        monthly_loyalty_trend=monthly_loyalty_trend,
        demographics=CustomersDemographics(
            by_sex=by_sex,
            by_age_band=by_age_band,
            by_region=by_region,
        ),
    )
