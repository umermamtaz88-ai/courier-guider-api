import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.auth import CurrentUser, require_tenant
from app.services.workflow.workflow_service import IssueService

router = APIRouter()
issue_router = APIRouter()


class IssueCreate(BaseModel):
    issue_type: str
    title: str
    description: str | None = None
    severity: str = "medium"
    source_data: dict | None = None


class IssueUpdate(BaseModel):
    status: str | None = None
    severity: str | None = None


@router.get("/{shipment_id}/issues")
async def list_issues(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = IssueService(db)
    issues = await service.list_for_shipment(current.tenant_id, shipment_id)
    return [
        {"id": str(i.id), "issue_type": i.issue_type, "title": i.title, "severity": i.severity, "status": i.status}
        for i in issues
    ]


@router.post("/{shipment_id}/issues")
async def create_issue(
    shipment_id: uuid.UUID,
    data: IssueCreate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = IssueService(db)
    issue = await service.create(current.tenant_id, shipment_id, data.model_dump(), current.user.id)
    return {"id": str(issue.id), "status": issue.status}


@issue_router.patch("/{issue_id}")
async def update_issue(
    issue_id: uuid.UUID,
    data: IssueUpdate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = IssueService(db)
    issue = await service.update(current.tenant_id, issue_id, data.model_dump(exclude_none=True), current.user.id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return {"id": str(issue.id), "status": issue.status}
