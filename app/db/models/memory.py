"""Conversation and user memory for RAG-first Courier Guider."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid


class ConversationContext(Base, TimestampMixin):
    """Short memory — extracted shipping context for the active conversation."""

    __tablename__ = "conversation_contexts"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserMemory(Base, TimestampMixin):
    """Long memory — persistent user preferences and business context."""

    __tablename__ = "user_memories"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "memory_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    memory_key: Mapped[str] = mapped_column(String(100), nullable=False)
    memory_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="inferred")
    confidence: Mapped[float | None] = mapped_column(nullable=True)
