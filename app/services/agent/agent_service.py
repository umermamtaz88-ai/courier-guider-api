from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent import CourierGuiderAgent


class AgentService:
    """Facade for Courier Guider agent."""

    def __init__(self, db: AsyncSession):
        self.agent = CourierGuiderAgent(db)

    async def chat(self, **kwargs) -> dict:
        return await self.agent.run(**kwargs)
