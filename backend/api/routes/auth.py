import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.hash import pbkdf2_sha256
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import TenantModel, UserModel
from adapters.postgresql.repositories import TenantRepository, UserRepository
from api.middleware.auth import blacklist_token
from api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TenantResponse,
    TokenResponse,
    UserResponse,
)
from config.settings import get_settings
from core.models.tenant import Tenant, User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])

RATE_LIMIT_STORE: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str, max_attempts: int = 5, window_seconds: int = 60) -> None:
    now = time.time()
    window_start = now - window_seconds
    RATE_LIMIT_STORE[ip] = [t for t in RATE_LIMIT_STORE[ip] if t > window_start]
    if len(RATE_LIMIT_STORE[ip]) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )
    RATE_LIMIT_STORE[ip].append(now)


def create_access_token(data: dict) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expiration_minutes)
    to_encode.update({"exp": expire, "token_type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=30)
    to_encode.update({"exp": expire, "token_type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    tenant_repo = TenantRepository(session)
    user_repo = UserRepository(session)

    tenant_model = await tenant_repo.get_by_slug(body.tenant_slug)
    if not tenant_model:
        tenant = Tenant(name=body.tenant_slug, slug=body.tenant_slug)
        tenant_model = await tenant_repo.create(tenant)

    existing = await user_repo.get_by_email(str(tenant_model.id), body.email)
    if existing:
        return RegisterResponse(
            token="",
            user=UserResponse(
                id="",
                email=body.email,
                display_name="",
                role="",
            ),
            tenant=TenantResponse(
                id=str(tenant_model.id),
                name=tenant_model.name,
                slug=tenant_model.slug,
                status=tenant_model.status,
            ),
        )

    password_hash = pbkdf2_sha256.hash(body.password)
    user = User(
        tenant_id=str(tenant_model.id),
        email=body.email,
        display_name=body.display_name,
        role=UserRole.EDITOR,
    )
    user_model = await user_repo.create(user, password_hash)

    token = create_access_token({
        "sub": str(user_model.id),
        "tenant_id": str(tenant_model.id),
        "role": user_model.role,
        "email": user_model.email,
    })

    return RegisterResponse(
        token=token,
        user=UserResponse(
            id=str(user_model.id),
            email=user_model.email,
            display_name=user_model.display_name or "",
            role=user_model.role,
        ),
        tenant=TenantResponse(
            id=str(tenant_model.id),
            name=tenant_model.name,
            slug=tenant_model.slug,
            status=tenant_model.status,
        ),
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    _check_rate_limit(request.client.host if request.client else "unknown")

    settings = get_settings()
    query = select(UserModel).where(UserModel.email == body.email)
    if body.tenant_slug:
        tenant_result = await session.execute(
            select(TenantModel).where(TenantModel.slug == body.tenant_slug)
        )
        tenant_model = tenant_result.scalar_one_or_none()
        if tenant_model:
            query = query.where(UserModel.tenant_id == tenant_model.id)
    result = await session.execute(query)
    user_model = result.scalar_one_or_none()

    if not user_model or not pbkdf2_sha256.verify(body.password, user_model.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user_model.last_login_at = datetime.now(UTC)
    await session.flush()

    access_token = create_access_token({
        "sub": str(user_model.id),
        "tenant_id": str(user_model.tenant_id),
        "role": user_model.role,
        "email": user_model.email,
    })

    refresh_token = create_refresh_token({
        "sub": str(user_model.id),
        "tenant_id": str(user_model.tenant_id),
        "role": user_model.role,
        "email": user_model.email,
    })

    return LoginResponse(
        token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_expiration_minutes * 60,
        user=UserResponse(
            id=str(user_model.id),
            email=user_model.email,
            display_name=user_model.display_name or "",
            role=user_model.role,
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    settings = get_settings()
    token = body.refresh_token
    from api.middleware.auth import BLACKLISTED_TOKENS
    if token in BLACKLISTED_TOKENS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        role = payload.get("role")
        token_type = payload.get("token_type")
        if not user_id or not tenant_id or not role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type for refresh",
            )
        access_token = create_access_token({
            "sub": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "email": payload.get("email"),
        })
        return TokenResponse(
            access_token=access_token,
            expires_in=settings.jwt_expiration_minutes * 60,
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        blacklist_token(token)
    return {"detail": "Logged out successfully"}
