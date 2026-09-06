from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message
from app.db.session import get_db
from app.schemas.common import ChatRequest, ChatResponse
from app.security.auth import CurrentUser, require_tenant
from app.services.agent.agent_service import AgentService

router = APIRouter()


class UpdateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    status: str | None = None


@router.get("/conversations")
async def list_conversations(
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
    include_archived: bool = False,
):
    """List saved conversations for the current user."""
    filters = [
        Conversation.tenant_id == current.tenant_id,
        Conversation.user_id == current.user.id,
    ]
    if not include_archived:
        filters.append(Conversation.status != "archived")

    result = await db.execute(
        select(Conversation)
        .where(*filters)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    return [
        {
            "id": str(c.id),
            "title": c.title or "Untitled",
            "status": c.status or "active",
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in result.scalars().all()
    ]


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    data: UpdateConversationRequest,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Rename or change status (active / archived) for a conversation."""
    import uuid

    conv_id = uuid.UUID(conversation_id)
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.tenant_id == current.tenant_id,
            Conversation.user_id == current.user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if data.title is not None:
        cleaned = data.title.strip()
        if not cleaned:
            raise HTTPException(status_code=422, detail="Title cannot be empty.")
        conv.title = cleaned[:255]

    if data.status is not None:
        status = data.status.strip().lower()
        if status not in {"active", "archived"}:
            raise HTTPException(status_code=422, detail="Status must be active or archived.")
        conv.status = status

    await db.commit()
    await db.refresh(conv)
    return {
        "id": str(conv.id),
        "title": conv.title or "Untitled",
        "status": conv.status or "active",
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Load messages for a saved conversation."""
    import uuid

    conv_id = uuid.UUID(conversation_id)
    conv = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.tenant_id == current.tenant_id,
            Conversation.user_id == current.user.id,
        )
    )
    if conv.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in result.scalars().all()
    ]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and its related rows for the current user."""
    import uuid

    from sqlalchemy import delete as sa_delete

    from app.db.models import AgentRun
    from app.db.models.memory import ConversationContext

    conv_id = uuid.UUID(conversation_id)
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.tenant_id == current.tenant_id,
            Conversation.user_id == current.user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.execute(sa_delete(Message).where(Message.conversation_id == conv_id))
    await db.execute(sa_delete(AgentRun).where(AgentRun.conversation_id == conv_id))
    await db.execute(
        sa_delete(ConversationContext).where(ConversationContext.conversation_id == conv_id)
    )
    await db.delete(conv)
    await db.commit()
    return {"ok": True, "id": conversation_id}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Primary RAG-first courier advisor endpoint."""
    if not (data.message or "").strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    service = AgentService(db)
    result = await service.chat(
        tenant_id=current.tenant_id,
        user_id=current.user.id,
        message=data.message,
        conversation_id=data.conversation_id,
        shipment_id=data.shipment_id,
        priority=data.preferences.get("priority", "balanced"),
    )
    return ChatResponse(**result)
