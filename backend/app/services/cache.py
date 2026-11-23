"""Bounded thread-safe in-memory LRU cache for read-only analytical responses."""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, TypeVar

from .filters import GlobalFilters

T = TypeVar("T")


class BoundedLRUCache:
    """Thread-safe bounded LRU cache backed by OrderedDict."""

    def __init__(self, max_size: int = 256) -> None:
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        self.max_size = max_size
        self._lock = threading.RLock()
        self._data: OrderedDict[tuple[Any, ...], Any] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: tuple[Any, ...]) -> Any | None:
        with self._lock:
            if key not in self._data:
                self._misses += 1
                return None
            self._data.move_to_end(key)
            self._hits += 1
            return self._data[key]

    def set(self, key: tuple[Any, ...], value: Any) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            while len(self._data) > self.max_size:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "size": len(self._data),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
            }


def make_cache_key(
    endpoint: str,
    filters: GlobalFilters | None = None,
    *,
    ignore_dates: bool = False,
    **extras: Any,
) -> tuple[Any, ...]:
    """Build a canonical hashable cache key for an endpoint and its filter state."""
    filter_part: tuple[Any, ...] | None = None
    if filters is not None:
        filter_part = (
            None if ignore_dates else filters.start_date,
            None if ignore_dates else filters.end_date,
            filters.region_id,
            filters.store_id,
            filters.category_id,
            filters.subcategory_id,
        )
    extras_part = tuple(sorted(extras.items()))
    return (endpoint, filter_part, extras_part)


response_cache = BoundedLRUCache(max_size=256)


def cached_call(key: tuple[Any, ...], compute_fn: Callable[[], T]) -> T:
    """Return cached result for key or compute, store, and return."""
    hit = response_cache.get(key)
    if hit is not None:
        return hit
    value = compute_fn()
    response_cache.set(key, value)
    return value
