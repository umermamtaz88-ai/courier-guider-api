"""Reproduce web-search chat 500 and print stack trace."""

from __future__ import annotations

import asyncio
import traceback
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent import CourierGuiderAgent
from app.db.session import AsyncSessionLocal
from app.services.auth_service import AuthService


async def main() -> None:
    async with AsyncSessionLocal() as db:
        service = AuthService(db)
        user = await service.authenticate("demo@example.com", "demo12345")
        if not user:
            print("Login failed")
            return
        links = await service.get_user_tenants(user.id)
        tenant_id = links[0].tenant_id if links else None
        if not tenant_id:
            print("No tenant")
            return

        agent = CourierGuiderAgent(db)
        msg = "Search the web and tell me the latest information about Leopards relevant shipping services."
        try:
            result = await agent.run(
                tenant_id=tenant_id,
                user_id=user.id,
                message=msg,
            )
            await db.commit()
            print("SUCCESS")
            print("web_search_used:", result.get("web_search_used"))
            print("rag_used:", result.get("rag_used"))
            print("llm_success:", result.get("llm_success"))
            print("errors:", result.get("internal_error_codes"))
            print("answer:", result.get("answer", "")[:300])
        except Exception:
            await db.rollback()
            print("EXCEPTION:")
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
