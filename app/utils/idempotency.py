import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IdempotencyKey


async def get_idempotent_response(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    key: str,
    operation: str,
) -> dict | None:
    result = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.tenant_id == tenant_id,
            IdempotencyKey.key == key,
            IdempotencyKey.operation == operation,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    if record.expires_at and record.expires_at < datetime.now(UTC):
        return None
    return record.response


async def store_idempotent_response(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    key: str,
    operation: str,
    response: dict,
    ttl_hours: int = 24,
) -> None:
    db.add(
        IdempotencyKey(
            tenant_id=tenant_id,
            key=key,
            operation=operation,
            response=response,
            expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
        )
    )
    await db.flush()
