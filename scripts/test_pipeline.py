"""Run one chat pipeline query with structured logging."""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.ai.agent import CourierGuiderAgent
from app.db.models import TenantUser, User
from app.db.session import AsyncSessionLocal

TEST_QUERY = "I have 8kg clothes from Lahore to Karachi. Which courier is better?"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        user_result = await db.execute(select(User).where(User.email == "demo@example.com"))
        user = user_result.scalar_one()
        tenant_result = await db.execute(select(TenantUser).where(TenantUser.user_id == user.id))
        tenant_link = tenant_result.scalars().first()
        agent = CourierGuiderAgent(db)
        result = await agent.run(
            tenant_id=tenant_link.tenant_id,
            user_id=user.id,
            message=TEST_QUERY,
        )
        print(json.dumps(
            {
                "intent": result.get("intent"),
                "answer_type": result.get("answer_type"),
                "rag_used": result.get("rag_used"),
                "web_search_used": result.get("web_search_used"),
                "current_data_verified": result.get("current_data_verified"),
                "data_source": result.get("data_source"),
                "internal_error_codes": result.get("internal_error_codes"),
                "warnings": result.get("warnings"),
                "source_count": len(result.get("sources", [])),
                "recommendation_count": len(result.get("recommendations", [])),
                "answer_preview": result.get("answer", "")[:240],
            },
            indent=2,
        ))


if __name__ == "__main__":
    asyncio.run(main())
