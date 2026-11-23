"""Shared global filters, date proration, and data-hygiene predicates."""

from __future__ import annotations

import calendar
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException, Query

from ..config import settings

# Hygiene predicates baked into analytical SQL queries.
TEST_PROMO_EXCLUDE_SQL = (
    "o.id != 13 AND LOWER(o.nume) NOT LIKE '%test%' "
    "AND EXISTS (SELECT 1 FROM oferte_produse op_chk WHERE op_chk.id_oferta = o.id)"
)
ACTIVE_SKU_SQL = "p.activ = 1"
OPEN_STORE_SQL = "m.inchis_la IS NULL"


def _parse_iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {field_name} '{value}'. Expected YYYY-MM-DD.",
        ) from exc


@dataclass(frozen=True)
class GlobalFilters:
    start_date: str
    end_date: str
    region_id: int | None
    store_id: int | None
    category_id: int | None
    subcategory_id: int | None

    @property
    def start_dt(self) -> date:
        return date.fromisoformat(self.start_date)

    @property
    def end_dt(self) -> date:
        return date.fromisoformat(self.end_date)

    @property
    def start_ts(self) -> str:
        return f"{self.start_date} 00:00:00"

    @property
    def end_ts_excl(self) -> str:
        return f"{(self.end_dt + timedelta(days=1)).isoformat()} 00:00:00"

    @property
    def has_category_filter(self) -> bool:
        return self.category_id is not None or self.subcategory_id is not None


def get_global_filters(
    start_date: str = Query(default=settings.default_start_date, description="Inclusive YYYY-MM-DD"),
    end_date: str = Query(default=settings.default_end_date, description="Inclusive YYYY-MM-DD"),
    region_id: int | None = Query(default=None, ge=1),
    store_id: int | None = Query(default=None, ge=1),
    category_id: int | None = Query(default=None, ge=1),
    subcategory_id: int | None = Query(default=None, ge=1),
) -> GlobalFilters:
    s_dt = _parse_iso_date(start_date, "start_date")
    e_dt = _parse_iso_date(end_date, "end_date")
    if s_dt > e_dt:
        raise HTTPException(
            status_code=422,
            detail=f"start_date ({start_date}) must be <= end_date ({end_date}).",
        )
    return GlobalFilters(
        start_date=s_dt.isoformat(),
        end_date=e_dt.isoformat(),
        region_id=region_id,
        store_id=store_id,
        category_id=category_id,
        subcategory_id=subcategory_id,
    )


def get_store_trend_filters(
    start_date: str = Query(default=settings.default_start_date, description="Inclusive YYYY-MM-DD"),
    end_date: str = Query(default=settings.default_end_date, description="Inclusive YYYY-MM-DD"),
    region_id: int | None = Query(default=None, ge=1),
    category_id: int | None = Query(default=None, ge=1),
    subcategory_id: int | None = Query(default=None, ge=1),
) -> GlobalFilters:
    """Filter dependency for /stores/{store_id}/trend where store_id is a path param."""
    return get_global_filters(
        start_date=start_date,
        end_date=end_date,
        region_id=region_id,
        store_id=None,
        category_id=category_id,
        subcategory_id=subcategory_id,
    )


def build_sales_where(
    filters: GlobalFilters,
    *,
    include_dates: bool = True,
    bonuri_alias: str = "b",
    vanzari_alias: str = "v",
    magazine_alias: str = "m",
    produse_alias: str = "p",
    categorii_alias: str = "c",
) -> tuple[str, dict[str, Any], bool, bool, bool]:
    """Build parameterized WHERE clause and join flags for bonuri/vanzari queries."""
    clauses: list[str] = []
    params: dict[str, Any] = {}
    needs_magazine = False
    needs_produse = False
    needs_categorii = False

    if include_dates and not (
        filters.start_date <= settings.default_start_date
        and filters.end_date >= settings.default_end_date
    ):
        clauses.append(f"{bonuri_alias}.cand >= :start_ts AND {bonuri_alias}.cand < :end_ts_excl")
        params["start_ts"] = filters.start_ts
        params["end_ts_excl"] = filters.end_ts_excl

    if filters.store_id is not None:
        clauses.append(f"{bonuri_alias}.id_magazin = :store_id")
        params["store_id"] = filters.store_id

    if filters.region_id is not None:
        needs_magazine = True
        clauses.append(f"{magazine_alias}.id_regiune = :region_id")
        params["region_id"] = filters.region_id

    if filters.subcategory_id is not None:
        needs_produse = True
        clauses.append(f"{produse_alias}.id_categorie = :subcategory_id")
        params["subcategory_id"] = filters.subcategory_id
    elif filters.category_id is not None:
        needs_produse = True
        clauses.append(
            f"{produse_alias}.id_categorie IN "
            "(SELECT id FROM categorii WHERE id = :category_id OR id_parinte = :category_id)"
        )
        params["category_id"] = filters.category_id

    where_sql = " AND ".join(clauses) if clauses else "1=1"
    return where_sql, params, needs_magazine, needs_produse, needs_categorii


def sales_joins_sql(
    needs_magazine: bool,
    needs_produse: bool,
    needs_categorii: bool,
    *,
    bonuri_alias: str = "b",
    vanzari_alias: str = "v",
) -> str:
    parts: list[str] = []
    if needs_magazine:
        parts.append(f"JOIN magazine m ON m.id = {bonuri_alias}.id_magazin")
    if needs_produse or needs_categorii:
        parts.append(f"JOIN produse p ON p.id = {vanzari_alias}.id_produs")
    if needs_categorii:
        parts.append("JOIN categorii c ON c.id = p.id_categorie")
    return "\n".join(parts)


def month_overlap_weights(start_dt: date, end_dt: date) -> dict[str, float]:
    """Return {YYYY-MM: overlap_fraction} for every month overlapping [start_dt, end_dt]."""
    weights: dict[str, float] = {}
    y, m = start_dt.year, start_dt.month
    end_ym = (end_dt.year, end_dt.month)
    while (y, m) <= end_ym:
        days_in_month = calendar.monthrange(y, m)[1]
        m_start = date(y, m, 1)
        m_end = date(y, m, days_in_month)
        ov_start = max(start_dt, m_start)
        ov_end = min(end_dt, m_end)
        overlap_days = (ov_end - ov_start).days + 1
        weights[f"{y:04d}-{m:02d}"] = overlap_days / days_in_month
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return weights


def compute_targets(
    conn: sqlite3.Connection, filters: GlobalFilters
) -> dict[str, Any]:
    """Compute prorated targets by total, month, store, and region.

    Returns target_available=False when a category or subcategory filter is active.
    """
    if filters.has_category_filter:
        return {
            "target_available": False,
            "total_target_ron": None,
            "by_month": {},
            "by_store": {},
            "by_region": {},
        }

    weights = month_overlap_weights(filters.start_dt, filters.end_dt)
    if not weights:
        return {
            "target_available": True,
            "total_target_ron": 0.0,
            "by_month": {},
            "by_store": {},
            "by_region": {},
        }

    months = sorted(weights.keys())
    placeholders = ",".join("?" for _ in months)
    params: list[Any] = list(months)
    where_extra: list[str] = []
    if filters.region_id is not None:
        where_extra.append("m.id_regiune = ?")
        params.append(filters.region_id)
    if filters.store_id is not None:
        where_extra.append("t.id_magazin = ?")
        params.append(filters.store_id)

    extra_sql = (" AND " + " AND ".join(where_extra)) if where_extra else ""
    rows = conn.execute(
        f"""
        SELECT t.id_magazin, m.id_regiune, t.luna, t.target_vanzari
        FROM target_lunar t
        JOIN magazine m ON m.id = t.id_magazin
        WHERE t.luna IN ({placeholders}) {extra_sql}
        """,
        params,
    ).fetchall()

    total = 0.0
    by_month: dict[str, float] = {}
    by_store: dict[int, float] = {}
    by_region: dict[int, float] = {}

    for r in rows:
        luna = r["luna"]
        prorated = float(r["target_vanzari"]) * weights[luna]
        total += prorated
        by_month[luna] = by_month.get(luna, 0.0) + prorated
        sid = int(r["id_magazin"])
        rid = int(r["id_regiune"])
        by_store[sid] = by_store.get(sid, 0.0) + prorated
        by_region[rid] = by_region.get(rid, 0.0) + prorated

    return {
        "target_available": True,
        "total_target_ron": round(total, 2),
        "by_month": {k: round(v, 2) for k, v in by_month.items()},
        "by_store": {k: round(v, 2) for k, v in by_store.items()},
        "by_region": {k: round(v, 2) for k, v in by_region.items()},
    }
