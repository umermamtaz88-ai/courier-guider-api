import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ShipmentIssue, Task
from app.utils.audit import write_audit


class IssueService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_shipment(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> list[ShipmentIssue]:
        result = await self.db.execute(
            select(ShipmentIssue).where(
                ShipmentIssue.tenant_id == tenant_id,
                ShipmentIssue.shipment_id == shipment_id,
            )
        )
        return list(result.scalars().all())

    async def create(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID, data: dict, user_id: uuid.UUID) -> ShipmentIssue:
        issue = ShipmentIssue(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            issue_type=data["issue_type"],
            severity=data.get("severity", "medium"),
            title=data["title"],
            description=data.get("description"),
            source_data=data.get("source_data"),
        )
        self.db.add(issue)
        await self.db.flush()
        await write_audit(
            self.db, tenant_id=tenant_id, user_id=user_id, action="issue_created",
            entity_type="shipment_issue", entity_id=issue.id, after=data,
        )
        return issue

    async def update(self, tenant_id: uuid.UUID, issue_id: uuid.UUID, data: dict, user_id: uuid.UUID) -> ShipmentIssue | None:
        result = await self.db.execute(
            select(ShipmentIssue).where(ShipmentIssue.id == issue_id, ShipmentIssue.tenant_id == tenant_id)
        )
        issue = result.scalar_one_or_none()
        if issue is None:
            return None
        if "status" in data:
            issue.status = data["status"]
        if "severity" in data:
            issue.severity = data["severity"]
        await self.db.flush()
        await write_audit(
            self.db, tenant_id=tenant_id, user_id=user_id, action="issue_updated",
            entity_type="shipment_issue", entity_id=issue.id, after=data,
        )
        return issue


class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_tenant(self, tenant_id: uuid.UUID, status: str | None = None) -> list[Task]:
        stmt = select(Task).where(Task.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Task.status == status)
        result = await self.db.execute(stmt.order_by(Task.created_at.desc()))
        return list(result.scalars().all())

    async def get(self, tenant_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
        result = await self.db.execute(
            select(Task).where(Task.id == task_id, Task.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def create(self, tenant_id: uuid.UUID, data: dict, user_id: uuid.UUID) -> Task:
        task = Task(
            tenant_id=tenant_id,
            shipment_id=data.get("shipment_id"),
            title=data["title"],
            description=data.get("description"),
            priority=data.get("priority", "medium"),
            assigned_to=data.get("assigned_to"),
        )
        self.db.add(task)
        await self.db.flush()
        await write_audit(
            self.db, tenant_id=tenant_id, user_id=user_id, action="task_created",
            entity_type="task", entity_id=task.id, after=data,
        )
        return task

    async def update(self, tenant_id: uuid.UUID, task_id: uuid.UUID, data: dict, user_id: uuid.UUID) -> Task | None:
        task = await self.get(tenant_id, task_id)
        if task is None:
            return None
        for field in ("title", "description", "status", "priority", "assigned_to"):
            if field in data and data[field] is not None:
                setattr(task, field, data[field])
        await self.db.flush()
        await write_audit(
            self.db, tenant_id=tenant_id, user_id=user_id, action="task_updated",
            entity_type="task", entity_id=task.id, after=data,
        )
        return task
