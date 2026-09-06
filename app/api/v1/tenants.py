import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Tenant, TenantRole, TenantUser
from app.db.session import get_db
from app.schemas.common import TenantCreate, TenantResponse
from app.security.auth import CurrentUser, get_current_user, require_tenant

router = APIRouter()


class TenantUpdate(BaseModel):
    name: str | None = None


@router.post("", response_model=TenantResponse)
async def create_tenant(
    data: TenantCreate,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    slug = data.name.lower().replace(" ", "-")[:50] + f"-{uuid.uuid4().hex[:6]}"
    tenant = Tenant(name=data.name, slug=slug)
    db.add(tenant)
    await db.flush()
    db.add(TenantUser(tenant_id=tenant.id, user_id=current.user.id, role=TenantRole.OWNER))
    await db.flush()
    return tenant


@router.get("", response_model=list[TenantResponse])
async def list_tenants(current: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Tenant).join(TenantUser).where(TenantUser.user_id == current.user.id)
    )
    return list(result.scalars().all())


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one()


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID,
    data: TenantUpdate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if data.name:
        tenant.name = data.name
    await db.flush()
    return tenant
