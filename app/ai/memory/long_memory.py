import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserMemory

ALLOWED_KEYS = {
    "preferred_priority",
    "default_origin",
    "usual_product",
    "uses_cod",
    "business_location",
}


class LongMemoryService:
    """Persistent user preferences for personalized recommendations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def load(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(UserMemory).where(
                UserMemory.tenant_id == tenant_id,
                UserMemory.user_id == user_id,
            )
        )
        return {m.memory_key: m.memory_value for m in result.scalars().all()}

    async def remember(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        key: str,
        value: dict,
        source: str = "inferred",
        confidence: float = 0.7,
    ) -> None:
        if key not in ALLOWED_KEYS:
            return

        result = await self.db.execute(
            select(UserMemory).where(
                UserMemory.tenant_id == tenant_id,
                UserMemory.user_id == user_id,
                UserMemory.memory_key == key,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            self.db.add(
                UserMemory(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    memory_key=key,
                    memory_value=value,
                    source=source,
                    confidence=confidence,
                )
            )
        else:
            row.memory_value = value
            row.confidence = confidence
        await self.db.flush()

    def infer_from_message(self, message: str, parsed_context: dict) -> list[tuple[str, dict]]:
        lower = message.lower()
        updates: list[tuple[str, dict]] = []

        if "prefer" in lower and ("cheap" in lower or "low cost" in lower):
            updates.append(("preferred_priority", {"value": "cheapest"}))
        if parsed_context.get("origin"):
            updates.append(("default_origin", {"value": parsed_context["origin"]}))
        if parsed_context.get("product"):
            updates.append(("usual_product", {"value": parsed_context["product"]}))
        if parsed_context.get("cod") is True:
            updates.append(("uses_cod", {"value": True}))
        return updates
