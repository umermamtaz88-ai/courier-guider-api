import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.auth import CurrentUser, require_tenant
from app.services.workflow.workflow_service import TaskService

router = APIRouter()


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    shipment_id: uuid.UUID | None = None
    priority: str = "medium"
    assigned_to: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    assigned_to: uuid.UUID | None = None


@router.get("")
async def list_tasks(
    status: str | None = None,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = TaskService(db)
    tasks = await service.list_for_tenant(current.tenant_id, status)
    return [{"id": str(t.id), "title": t.title, "status": t.status, "priority": t.priority} for t in tasks]


@router.post("")
async def create_task(
    data: TaskCreate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = TaskService(db)
    task = await service.create(current.tenant_id, data.model_dump(), current.user.id)
    return {"id": str(task.id), "status": task.status}


@router.get("/{task_id}")
async def get_task(
    task_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = TaskService(db)
    task = await service.get(current.tenant_id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return {"id": str(task.id), "title": task.title, "status": task.status, "priority": task.priority}


@router.patch("/{task_id}")
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = TaskService(db)
    task = await service.update(current.tenant_id, task_id, data.model_dump(exclude_none=True), current.user.id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return {"id": str(task.id), "status": task.status}
