import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.workflow.workflow_service import TaskService


class TaskTools:
    def __init__(self, db: AsyncSession):
        self.service = TaskService(db)

    async def create_task(self, tenant_id: uuid.UUID, user_id: uuid.UUID, data: dict) -> dict:
        task = await self.service.create(tenant_id, data, user_id)
        return {"id": str(task.id), "title": task.title, "status": task.status}

    async def update_task(self, tenant_id: uuid.UUID, user_id: uuid.UUID, task_id: uuid.UUID, data: dict) -> dict | None:
        task = await self.service.update(tenant_id, task_id, data, user_id)
        if task is None:
            return None
        return {"id": str(task.id), "title": task.title, "status": task.status}

    async def list_tasks(self, tenant_id: uuid.UUID) -> list[dict]:
        tasks = await self.service.list_for_tenant(tenant_id)
        return [{"id": str(t.id), "title": t.title, "status": t.status, "priority": t.priority} for t in tasks]
