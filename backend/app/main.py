"""FastAPI application entry point for Farmacia Lumen BI & Operations API."""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import get_ro_connection
from .routers import alerts, analyst, customers, inventory, overview, promotions, stores
from .services.filters import GlobalFilters


def _warm_default_views() -> None:
    """Pre-populate the in-memory LRU cache for default unfiltered endpoints."""
    default_filters = GlobalFilters(
        start_date=settings.default_start_date,
        end_date=settings.default_end_date,
        region_id=None,
        store_id=None,
        category_id=None,
        subcategory_id=None,
    )
    conn = get_ro_connection()
    try:
        overview.get_filters(conn=conn)
        overview.get_overview(granularity="month", filters=default_filters, conn=conn)
        stores.get_stores(sort_by="attainment_pct", filters=default_filters, conn=conn)
        promotions.get_promotions(filters=default_filters, conn=conn)
        inventory.get_inventory(low_stock_max=5, limit=50, filters=default_filters, conn=conn)
        customers.get_customers(filters=default_filters, conn=conn)
        alerts.get_alerts(severity=None, category=None, filters=default_filters, conn=conn)
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    conn = get_ro_connection()
    conn.execute("SELECT 1").fetchone()
    conn.close()

    warmup_task: asyncio.Task[None] | None = None
    if settings.warm_cache_on_startup:
        warmup_task = asyncio.create_task(asyncio.to_thread(_warm_default_views))
    try:
        yield
    finally:
        if warmup_task is not None and not warmup_task.done():
            warmup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await warmup_task


app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(overview.router, prefix=API_PREFIX)
app.include_router(stores.router, prefix=API_PREFIX)
app.include_router(promotions.router, prefix=API_PREFIX)
app.include_router(inventory.router, prefix=API_PREFIX)
app.include_router(customers.router, prefix=API_PREFIX)
app.include_router(alerts.router, prefix=API_PREFIX)
app.include_router(analyst.router, prefix=API_PREFIX)
