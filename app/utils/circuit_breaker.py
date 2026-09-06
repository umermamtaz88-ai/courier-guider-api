import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IntegrationHealth

FAILURE_THRESHOLD = 5


class CircuitBreakerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_or_create(self, integration_type: str, integration_name: str) -> IntegrationHealth:
        result = await self.db.execute(
            select(IntegrationHealth).where(
                IntegrationHealth.integration_type == integration_type,
                IntegrationHealth.integration_name == integration_name,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            record = IntegrationHealth(
                integration_type=integration_type,
                integration_name=integration_name,
                status="healthy",
                failure_count=0,
                circuit_open=False,
            )
            self.db.add(record)
            await self.db.flush()
        return record

    async def is_open(self, integration_type: str, integration_name: str) -> bool:
        record = await self._get_or_create(integration_type, integration_name)
        return record.circuit_open

    async def record_success(self, integration_type: str, integration_name: str) -> None:
        record = await self._get_or_create(integration_type, integration_name)
        record.status = "healthy"
        record.failure_count = 0
        record.circuit_open = False
        record.last_success_at = datetime.now(UTC)
        await self.db.flush()

    async def record_failure(self, integration_type: str, integration_name: str, error: str) -> None:
        record = await self._get_or_create(integration_type, integration_name)
        record.failure_count += 1
        record.last_error_at = datetime.now(UTC)
        record.last_error_message = error[:500]
        if record.failure_count >= FAILURE_THRESHOLD:
            record.circuit_open = True
            record.status = "circuit_open"
        else:
            record.status = "degraded"
        await self.db.flush()
