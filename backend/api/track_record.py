"""Public track-record endpoints.

These are deliberately unauthenticated so anyone can audit the published
history. They expose only platform-wide, live-resolved signal rows; see
:mod:`backend.services.track_record_service` for the filtering rules.
"""
from __future__ import annotations

import asyncio
import hashlib
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.db.supabase import SupabaseDB, get_service_client
from backend.middleware.rate_limiter import check_public_rate_limit
from backend.services import track_record_service

router = APIRouter(prefix="/api", tags=["track-record"])

CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=300"
SNAPSHOT_TIMEOUT = 25


async def _snapshot(*, recent_limit: int = 50) -> dict:
    client = await get_service_client()
    return await track_record_service.snapshot(
        SupabaseDB(client), recent_limit=recent_limit
    )


@router.get("/track-record")
async def get_track_record(request: Request):
    check_public_rate_limit(request, bucket="track-record")
    try:
        payload = await asyncio.wait_for(_snapshot(), timeout=SNAPSHOT_TIMEOUT)
    except Exception:
        return JSONResponse(
            {"error": "track_record_unavailable"},
            status_code=503,
            headers={"Retry-After": "30", "Cache-Control": "no-store"},
        )

    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    etag = '"' + hashlib.sha256(body).hexdigest() + '"'
    headers = {
        "Cache-Control": CACHE_CONTROL,
        "ETag": etag,
        "X-Track-Record-Version": payload.get("resolution_version", ""),
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


@router.get("/track-record.csv")
async def get_track_record_csv(request: Request):
    check_public_rate_limit(request, bucket="track-record-csv")
    try:
        payload = await asyncio.wait_for(
            _snapshot(recent_limit=track_record_service.MAX_ROWS),
            timeout=SNAPSHOT_TIMEOUT,
        )
    except Exception:
        return Response(
            content="error\n",
            status_code=503,
            media_type="text/plain; charset=utf-8",
            headers={"Retry-After": "30", "Cache-Control": "no-store"},
        )

    text = track_record_service.rows_to_csv(payload.get("recent") or [])
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": CACHE_CONTROL,
            "Content-Disposition": 'attachment; filename="orqeva-track-record.csv"',
            "X-Track-Record-Version": payload.get("resolution_version", ""),
        },
    )
