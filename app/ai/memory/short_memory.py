import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.query_parser import ParsedQuery, parse_query
from app.db.models import ConversationContext, Message


class ShortMemoryService:
    """Extract and persist shipping context from the current conversation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def load(self, conversation_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(ConversationContext).where(ConversationContext.conversation_id == conversation_id)
        )
        ctx = result.scalar_one_or_none()
        return ctx.context if ctx else {}

    async def get_recent_messages(self, conversation_id: uuid.UUID, limit: int = 8) -> list[str]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return [m.content for m in reversed(list(result.scalars().all()))]

    async def build_context(
        self,
        *,
        conversation_id: uuid.UUID,
        tenant_id: uuid.UUID,
        message: str,
        intent: str,
    ) -> ParsedQuery:
        stored = await self.load(conversation_id)
        recent = await self.get_recent_messages(conversation_id)
        combined = " ".join(recent + [message])
        parsed = parse_query(combined, intent=intent)
        if stored:
            parsed.merge(stored)
        return parsed

    async def save(self, conversation_id: uuid.UUID, tenant_id: uuid.UUID, context: dict) -> None:
        result = await self.db.execute(
            select(ConversationContext).where(ConversationContext.conversation_id == conversation_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = ConversationContext(
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                context=context,
                last_message_at=datetime.now(UTC),
            )
            self.db.add(row)
        else:
            merged = {**row.context, **{k: v for k, v in context.items() if v is not None}}
            row.context = merged
            row.last_message_at = datetime.now(UTC)
        await self.db.flush()

    def context_from_parsed(self, parsed: ParsedQuery) -> dict:
        return {
            k: v
            for k, v in {
                "product": parsed.product,
                "weight_kg": parsed.weight_kg,
                "origin": parsed.origin,
                "destination": parsed.destination,
                "domestic": parsed.domestic,
                "international": parsed.international,
                "cod": parsed.cod,
                "priority": parsed.priority,
                "providers": parsed.providers,
            }.items()
            if v is not None
        }
