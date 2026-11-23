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
from ..services.cache import cached_call, make_cache_key
from ..services.filters import (
    GlobalFilters,
    build_sales_where,
    get_global_filters,
    sales_joins_sql,
)

router = APIRouter(tags=["customers"])

AGE_BAND_ORDER = ["<25", "25–34", "35–44", "45–54", "55–64", "65+"]


def _age_band(age: int) -> str:
    if age < 25:
        return "<25"
    if age <= 34:
        return "25–34"
    if age <= 44:
        return "35–44"
    if age <= 54:
        return "45–54"
    if age <= 64:
        return "55–64"
    return "65+"


@router.get("/customers", response_model=CustomersResponse)
def get_customers(
    filters: GlobalFilters = Depends(get_global_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> CustomersResponse:
    def _compute() -> CustomersResponse:
        where_sql, params, needs_mag, needs_prod, needs_cat = build_sales_where(filters)
        joins_sql = sales_joins_sql(needs_mag, needs_prod, needs_cat)

        # Scan 1: Monthly loyalty trend + card vs no-card penetration (tot_rec = card_rec + nocard_rec)
        trend_rows = query_all(
            conn,
            f"""
            SELECT substr(b.cand, 1, 7) AS period,
                   COUNT(DISTINCT CASE WHEN b.id_client IS NOT NULL THEN b.id END) AS card_rec,
                   COUNT(DISTINCT CASE WHEN b.id_client IS NULL THEN b.id END) AS nocard_rec,
                   COALESCE(SUM(CASE WHEN b.id_client IS NOT NULL THEN v.valoare_fara_tva ELSE 0 END), 0) AS card_rev,
                   COALESCE(SUM(CASE WHEN b.id_client IS NULL THEN v.valoare_fara_tva ELSE 0 END), 0) AS nocard_rev,
                   COALESCE(SUM(CASE WHEN b.id_client IS NOT NULL THEN v.profit ELSE 0 END), 0) AS card_prof,
                   COALESCE(SUM(CASE WHEN b.id_client IS NULL THEN v.profit ELSE 0 END), 0) AS nocard_prof
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

        monthly_loyalty_trend = []
        for r in trend_rows:
            cr = int(r["card_rec"])
            nr = int(r["nocard_rec"])
            tr = cr + nr
            monthly_loyalty_trend.append(
                MonthlyLoyaltyPoint(
                    period=r["period"],
                    card_share_pct=round(100.0 * cr / tr, 2) if tr else 0.0,
                    card_aov_ron=round(float(r["card_rev"]) / cr, 2) if cr else 0.0,
                    nocard_aov_ron=round(float(r["nocard_rev"]) / nr, 2) if nr else 0.0,
                )
            )

        # Scan 2: Per-client visits & spend for loyalty card transactions (feeds frequency + all 3 demographics)
        spend_rows = query_all(
            conn,
            f"""
            SELECT b.id_client,
                   COUNT(DISTINCT b.id) AS visits,
                   COALESCE(SUM(v.valoare_fara_tva), 0) AS spend
            FROM bonuri b
            JOIN vanzari v ON v.id_bon = b.id
            {joins_sql}
            WHERE b.id_client IS NOT NULL AND ({where_sql})
            GROUP BY b.id_client
            """,
            params,
        )
        client_spend: dict[int, tuple[int, float]] = {
            int(r["id_client"]): (int(r["visits"]), float(r["spend"]))
            for r in spend_rows
        }

        ref_row = query_one(conn, "SELECT CAST(substr(cand, 1, 4) AS INT) AS y FROM bonuri ORDER BY cand DESC LIMIT 1")
        ref_year = int(ref_row["y"]) if ref_row and ref_row["y"] else 2026

        region_names = {
            int(r["id"]): r["nume"]
            for r in query_all(conn, "SELECT id, nume FROM regiuni")
        }
        client_rows = query_all(conn, "SELECT id, sex, an_nasterii, id_regiune FROM clienti")
        clients_by_id = {int(r["id"]): r for r in client_rows}

        # Frequency buckets across registered members (optionally scoped by member's region_id)
        freq_acc: dict[int, list[object]] = {
            1: ["0 visits (Dormant)", 0, 0.0],
            2: ["1 visit (One-time)", 0, 0.0],
            3: ["2–5 visits", 0, 0.0],
            4: ["6–20 visits", 0, 0.0],
            5: ["20+ visits (VIP)", 0, 0.0],
        }
        total_members = 0
        for c in client_rows:
            if filters.region_id is not None and int(c["id_regiune"]) != filters.region_id:
                continue
            total_members += 1
            visits, spend = client_spend.get(int(c["id"]), (0, 0.0))
            if visits == 0:
                ord_key = 1
            elif visits == 1:
                ord_key = 2
            elif visits <= 5:
                ord_key = 3
            elif visits <= 20:
                ord_key = 4
            else:
                ord_key = 5
            freq_acc[ord_key][1] = int(freq_acc[ord_key][1]) + 1
            freq_acc[ord_key][2] = float(freq_acc[ord_key][2]) + spend

        dormant_members = int(freq_acc[1][1])
        one_time_members = int(freq_acc[2][1])
        frequency_segments = [
            FrequencySegmentItem(
                bucket=str(freq_acc[k][0]),
                members=int(freq_acc[k][1]),
                share_pct=round(100.0 * int(freq_acc[k][1]) / total_members, 2)
                if total_members
                else 0.0,
                revenue_ron=round(float(freq_acc[k][2]), 2),
                avg_spend_ron=round(float(freq_acc[k][2]) / int(freq_acc[k][1]), 2)
                if int(freq_acc[k][1])
                else 0.0,
            )
            for k in (1, 2, 3, 4, 5)
        ]

        # Demographics across active cardholders in filtered scope
        sex_acc: dict[str, list[float | int]] = {}
        age_acc: dict[str, list[float | int]] = {}
        reg_acc: dict[str, list[float | int]] = {}

        for cid, (visits, spend) in client_spend.items():
            c = clients_by_id.get(cid)
            if c is None:
                continue
            sex_lbl = str(c["sex"])
            age_lbl = _age_band(ref_year - int(c["an_nasterii"]))
            reg_lbl = region_names.get(int(c["id_regiune"]), "Unknown")

            for bucket_map, lbl in ((sex_acc, sex_lbl), (age_acc, age_lbl), (reg_acc, reg_lbl)):
                entry = bucket_map.get(lbl)
                if entry is None:
                    bucket_map[lbl] = [1, visits, spend]
                else:
                    entry[0] = int(entry[0]) + 1
                    entry[1] = int(entry[1]) + visits
                    entry[2] = float(entry[2]) + spend

        def _to_buckets(acc: dict[str, list[float | int]], order: list[str] | None = None) -> list[DemographicBucket]:
            items = [
                DemographicBucket(
                    label=lbl,
                    members=int(vals[0]),
                    receipts=int(vals[1]),
                    revenue_ron=round(float(vals[2]), 2),
                    avg_spend_per_member_ron=round(float(vals[2]) / int(vals[0]), 2)
                    if int(vals[0])
                    else 0.0,
                )
                for lbl, vals in acc.items()
            ]
            if order is not None:
                rank = {lbl: idx for idx, lbl in enumerate(order)}
                items.sort(key=lambda b: rank.get(b.label, 999))
            else:
                items.sort(key=lambda b: b.revenue_ron, reverse=True)
            return items

        return CustomersResponse(
            currency=settings.currency_label,
            total_registered_members=total_members,
            dormant_members=dormant_members,
            one_time_members=one_time_members,
            penetration=penetration,
            frequency_segments=frequency_segments,
            monthly_loyalty_trend=monthly_loyalty_trend,
            demographics=CustomersDemographics(
                by_sex=_to_buckets(sex_acc),
                by_age_band=_to_buckets(age_acc, order=AGE_BAND_ORDER),
                by_region=_to_buckets(reg_acc),
            ),
        )

    return cached_call(make_cache_key("customers", filters), _compute)
