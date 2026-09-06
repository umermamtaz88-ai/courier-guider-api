from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/{provider}")
async def provider_webhook(provider: str, request: Request):
    """Webhook ingress — verify signature in production."""
    payload = await request.json()
    return {
        "status": "received",
        "provider": provider,
        "event_id": payload.get("event_id") or payload.get("id"),
        "note": "Webhook stored for processing — implement signature verification before production",
    }
