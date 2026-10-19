"""Gateway webhooks: verified, idempotent, auto-approving.

POST /api/billing/webhooks/{provider} — signature-verified per provider,
deduped via payment_events (unique provider+event_id), then the matching
pending invoice is auto-approved and the subscription activated.
"""
import json

from fastapi import APIRouter, Depends, Request, Response

from backend.db.supabase import SupabaseDB, get_db
from backend.services import billing_service as billing

router = APIRouter(prefix="/api/billing/webhooks", tags=["billing-webhooks"])


@router.post("/{provider}")
async def gateway_webhook(
    provider: str,
    request: Request,
    db: SupabaseDB = Depends(get_db),
):
    body = await request.body()
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return Response(content='{"detail":"invalid json"}', status_code=400,
                        media_type="application/json")
    if not isinstance(payload, dict):
        return Response(content='{"detail":"invalid payload"}', status_code=400,
                        media_type="application/json")

    headers = {k.lower(): v for k, v in request.headers.items()}
    result = await billing.handle_gateway_webhook(db, provider, headers, body, payload)
    content = json.dumps({"detail": result.get("detail") or "ok",
                          "invoice_id": result.get("invoice_id")})
    return Response(content=content, status_code=int(result.get("status") or 200),
                    media_type="application/json")
