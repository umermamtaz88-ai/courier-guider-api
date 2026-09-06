import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Shipment,
    ShipmentDirection,
    ShipmentEvent,
    ShipmentStatus,
    Tenant,
    TenantRole,
    TenantUser,
    User,
    UserStatus,
)
from app.security.auth import hash_password


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, email: str, name: str, password: str, tenant_name: str) -> tuple[User, Tenant]:
        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ValueError("Email already registered")

        user = User(email=email, name=name, password_hash=hash_password(password), status=UserStatus.ACTIVE)
        slug = tenant_name.lower().replace(" ", "-")[:50]
        tenant = Tenant(name=tenant_name, slug=f"{slug}-{uuid.uuid4().hex[:6]}")
        self.db.add_all([user, tenant])
        await self.db.flush()

        link = TenantUser(tenant_id=tenant.id, user_id=user.id, role=TenantRole.OWNER)
        self.db.add(link)
        await self.db.flush()
        return user, tenant

    async def authenticate(self, email: str, password: str) -> User | None:
        from app.security.auth import verify_password

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None or not user.password_hash:
            return None
        if not verify_password(password, user.password_hash):
            return None
        user.last_login_at = datetime.now(UTC)
        return user

    async def get_user_tenants(self, user_id: uuid.UUID) -> list[TenantUser]:
        result = await self.db.execute(select(TenantUser).where(TenantUser.user_id == user_id))
        return list(result.scalars().all())
