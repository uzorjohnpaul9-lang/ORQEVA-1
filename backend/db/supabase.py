"""Supabase data + auth layer for the dashboard backend.

Backend talks to Supabase through two async clients created from the project
URL + keys (no Postgres connection strings):

  * service client  (SUPABASE_SERVICE_KEY)  -> admin auth + all PostgREST data
  * anon client     (SUPABASE_ANON_KEY)     -> public auth (sign in / sign up)

All CRUD goes through :class:`SupabaseDB`, a thin async facade over the
PostgREST API, so endpoints keep using ``await``.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from supabase import create_async_client
from supabase.lib.client_options import AsyncClientOptions

from backend.config import settings

_OPS = {"eq", "neq", "gt", "gte", "lt", "lte", "like", "ilike", "is", "match"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_dt(value: Any):
    """PostgREST returns timestamptz as ISO strings; normalise to UTC datetime."""
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _apply_filters(q, where: dict[str, Any] | None):
    """Turn an op-dict into PostgREST filter calls.

    Value forms:
      * plain value          -> eq
      * list                 -> in_
      * None                 -> is_
      * {"op": "gt", ...}    -> gt  (any of _OPS)
    """
    if not where:
        return q
    for col, val in where.items():
        if isinstance(val, dict) and "op" in val:
            op = val["op"]
            if op not in _OPS:
                raise ValueError(f"unsupported filter op {op!r}")
            q = getattr(q, op)(col, val["value"])
        elif isinstance(val, (list, tuple)):
            q = q.in_(col, list(val))
        elif val is None:
            q = q.is_(col, None)
        elif isinstance(val, bool):
            q = q.eq(col, val)
        else:
            q = q.eq(col, val)
    return q


def _apply_order(q, order: str | list[str] | None):
    if not order:
        return q
    orders = order if isinstance(order, list) else [order]
    for spec in orders:
        col, _, direction = spec.partition(".")
        q = q.order(col, desc=(direction == "desc"))
    return q


class SupabaseDB:
    """Async facade over the Supabase (PostgREST) data API."""

    def __init__(self, service_client):
        self._c = service_client

    # ---- reads ---------------------------------------------------------

    async def fetch_all(
        self,
        table: str,
        where: dict[str, Any] | None = None,
        order: str | list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        columns: str = "*",
    ) -> list[dict]:
        q = _apply_filters(self._c.table(table).select(columns), where)
        q = _apply_order(q, order)
        if limit is not None:
            q = q.limit(limit)
        if offset is not None:
            q = q.offset(offset)
        resp = await q.execute()
        return list(resp.data or [])

    async def fetch_one(
        self, table: str, where: dict[str, Any] | None = None, columns: str = "*"
    ) -> dict | None:
        q = _apply_filters(self._c.table(table).select(columns), where)
        q = q.limit(1)
        resp = await q.execute()
        rows = resp.data or []
        return rows[0] if rows else None

    async def count(self, table: str, where: dict[str, Any] | None = None) -> int:
        q = _apply_filters(self._c.table(table).select("id", count="exact"), where)
        resp = await q.execute()
        return int(resp.count or 0)

    # ---- writes --------------------------------------------------------

    async def insert(self, table: str, data: dict) -> dict:
        resp = await self._c.table(table).insert([data]).execute()
        rows = resp.data or []
        return rows[0] if rows else data

    async def insert_many(self, table: str, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        resp = await self._c.table(table).insert(rows).execute()
        return list(resp.data or [])

    async def update(
        self, table: str, data: dict, where: dict[str, Any] | None = None
    ) -> list[dict]:
        q = _apply_filters(self._c.table(table).update(data), where)
        resp = await q.execute()
        return list(resp.data or [])

    async def delete(self, table: str, where: dict[str, Any] | None = None) -> list[dict]:
        q = _apply_filters(self._c.table(table).delete(), where)
        resp = await q.execute()
        return list(resp.data or [])

    async def ping(self) -> bool:
        try:
            resp = await self._c.table("users").select("id").limit(1).execute()
            return True
        except Exception:
            return False


# ---- client lifecycle ----------------------------------------------------

_service_client: Any = None
_anon_client: Any = None
_lock = asyncio.Lock()


async def _get_client(key: str, anon: bool = False):
    global _service_client, _anon_client
    existing = _anon_client if anon else _service_client
    if existing is not None:
        return existing
    async with _lock:
        if anon:
            if _anon_client is None:
                _anon_client = await create_async_client(
                    settings.SUPABASE_URL,
                    settings.SUPABASE_PUBLISHABLE_KEY,
                    options=AsyncClientOptions(),
                )
            return _anon_client
        if _service_client is None:
            _service_client = await create_async_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SECRET_KEY,
                options=AsyncClientOptions(),
            )
        return _service_client


async def get_service_client():
    return await _get_client(settings.SUPABASE_SECRET_KEY)


async def get_anon_client():
    return await _get_client(settings.SUPABASE_PUBLISHABLE_KEY, anon=True)


async def get_db():
    """FastAPI dependency: one SupabaseDB facade per request (keeps ``Depends(get_db)``)."""
    client = await get_service_client()
    yield SupabaseDB(client)
