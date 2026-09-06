from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.common import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from pydantic import BaseModel

from app.errors import AUTHENTICATION_REQUIRED, INVALID_TOKEN, auth_error
from app.security.auth import decode_token, create_access_token, create_refresh_token, get_current_user, CurrentUser
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        user, tenant = await service.register(data.email, data.name, data.password, data.tenant_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    access = create_access_token(
        str(user.id),
        extra={"tenant_id": str(tenant.id), "role": "OWNER"},
    )
    refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh, tenant_id=tenant.id)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.authenticate(data.email, data.password)
    if user is None:
        raise auth_error(AUTHENTICATION_REQUIRED, "Invalid credentials.")

    tenant_id = data.tenant_id
    role = None
    if tenant_id is None:
        links = await service.get_user_tenants(user.id)
        if links:
            tenant_id = links[0].tenant_id
            role = links[0].role.value
    else:
        from app.security.auth import verify_tenant_membership

        link = await verify_tenant_membership(tenant_id, user.id, db)
        role = link.role.value

    access = create_access_token(
        str(user.id),
        extra={"tenant_id": str(tenant_id) if tenant_id else None, "role": role},
    )
    refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh, tenant_id=tenant_id)


@router.get("/me", response_model=UserResponse)
async def me(current: CurrentUser = Depends(get_current_user)):
    return current.user


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if payload.get("type") != "refresh":
        raise auth_error(INVALID_TOKEN, "Invalid refresh token.")
    import uuid

    user_id = uuid.UUID(payload["sub"])
    service = AuthService(db)
    links = await service.get_user_tenants(user_id)
    tenant_id = links[0].tenant_id if links else None
    role = links[0].role.value if links else None
    access = create_access_token(
        str(user_id),
        extra={"tenant_id": str(tenant_id) if tenant_id else None, "role": role},
    )
    refresh = create_refresh_token(str(user_id))
    return TokenResponse(access_token=access, refresh_token=refresh, tenant_id=tenant_id)

@router.post("/logout")
async def logout():
    return {"status": "logged_out"}
