import logging
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.hash import pbkdf2_sha256
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import UserModel
from adapters.postgresql.repositories import UserRepository
from adapters.redis.client import RedisClient
from api.middleware.auth import (
    _decode_token,
    blacklist_token,
)
from api.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from config.settings import get_settings
from core.models.user import User, UserRole

logger = logging.getLogger("docforge")

router = APIRouter(prefix="/auth", tags=["auth"])


async def _check_rate_limit_redis(
    redis_key: str, max_requests: int = 5, window: int = 60
) -> None:
    redis = await RedisClient.get_client()
    if redis is None:
        return
    key = f"rate_limit:{redis_key}"
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, window)
    if current > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    host = request.client.host if request.client else "127.0.0.1"
    return host


def create_access_token(data: dict) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expiration_minutes)
    to_encode.update({
        "exp": expire,
        "token_type": "access",
        "jti": str(uuid.uuid4()),
    })
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=30)
    to_encode.update({
        "exp": expire,
        "token_type": "refresh",
        "jti": str(uuid.uuid4()),
    })
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    ip = _client_ip(request)
    await _check_rate_limit_redis(f"register:{ip}")

    user_repo = UserRepository(session)

    existing = await user_repo.get_by_email(body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists. Please log in.",
        )

    password_hash = pbkdf2_sha256.hash(body.password)
    user = User(
        email=body.email,
        display_name=body.display_name,
        role=UserRole.EDITOR,
    )
    user_model = await user_repo.create(user, password_hash)

    user_model.email_verified = False

    verify_token = str(uuid.uuid4())
    redis = await RedisClient.get_client()
    if redis is not None:
        await redis.setex(
            f"email_verify:{verify_token}",
            86400,
            str(user_model.id),
        )
    # NEVER log the token itself — it is a bearer credential. Deliver via email.
    logger.info("Email verification token generated", extra={
        "user_id": str(user_model.id),
    })

    token = create_access_token({
        "sub": str(user_model.id),
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
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    ip = _client_ip(request)
    await _check_rate_limit_redis(f"login:{ip}")

    settings = get_settings()
    result = await session.execute(
        select(UserModel).where(UserModel.email == body.email)
    )
    user_model = result.scalar_one_or_none()

    if not user_model or not pbkdf2_sha256.verify(body.password, user_model.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user_model.last_login_at = datetime.now(UTC)
    try:
        await session.flush()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A database conflict occurred during login. Please try again.",
        )

    access_token = create_access_token({
        "sub": str(user_model.id),
        "role": user_model.role,
        "email": user_model.email,
    })

    refresh_token = create_refresh_token({
        "sub": str(user_model.id),
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
async def refresh(
    body: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    ip = _client_ip(request)
    await _check_rate_limit_redis(f"refresh:{ip}")

    settings = get_settings()
    token = body.refresh_token
    payload = await _decode_token(token)
    token_type = payload.get("token_type")
    if token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for refresh",
        )
    user_id = payload.get("sub")
    role = payload.get("role")
    if not user_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    access_token = create_access_token({
        "sub": user_id,
        "role": role,
        "email": payload.get("email"),
    })
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_expiration_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        access_token = auth_header[7:]
        settings = get_settings()
        try:
            payload = jwt.decode(
                access_token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            )
            jti = payload.get("jti", access_token)
            await blacklist_token(access_token)
            user_id = payload.get("sub")
            if user_id:
                redis = await RedisClient.get_client()
                if redis is not None:
                    await redis.sadd(f"user:{user_id}:tokens", jti)
                    await redis.expire(f"user:{user_id}:tokens", 3600)
        except JWTError:
            logger.warning("Logout with invalid token")
    return {"detail": "Logged out successfully"}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    ip = _client_ip(request)
    await _check_rate_limit_redis(f"forgot_password:{ip}", max_requests=3, window=3600)

    result = await session.execute(
        select(UserModel).where(UserModel.email == body.email)
    )
    user_model = result.scalar_one_or_none()

    if not user_model:
        return {"detail": "If the email exists, a password reset link has been sent."}

    reset_token = str(uuid.uuid4())
    redis = await RedisClient.get_client()
    if redis is not None:
        await redis.setex(
            f"password_reset:{reset_token}",
            3600,
            str(user_model.id),
        )

    # NEVER log the reset token — it is a single-credential account-takeover vector.
    logger.info("Password reset token generated", extra={
        "user_id": str(user_model.id),
    })

    return {"detail": "If the email exists, a password reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    ip = _client_ip(request)
    await _check_rate_limit_redis(f"reset_password:{ip}", max_requests=3, window=3600)

    redis = await RedisClient.get_client()
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        )
    user_id = await redis.get(f"password_reset:{body.token}")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    result = await session.execute(
        select(UserModel).where(UserModel.id == UUID(user_id))
    )
    user_model = result.scalar_one_or_none()
    if not user_model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    user_model.password_hash = pbkdf2_sha256.hash(body.password)
    try:
        await session.flush()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A database conflict occurred while resetting the password. Please try again.",
        )

    if redis is not None:
        await redis.delete(f"password_reset:{body.token}")

    logger.info("Password reset successful", extra={"user_id": user_id})

    return {"detail": "Password reset successfully."}


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
):
    redis = await RedisClient.get_client()
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again later.",
        )
    user_id = await redis.get(f"email_verify:{body.token}")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    result = await session.execute(
        select(UserModel).where(UserModel.id == UUID(user_id))
    )
    user_model = result.scalar_one_or_none()
    if not user_model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    user_model.email_verified = True
    try:
        await session.flush()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A database conflict occurred while verifying the email. Please try again.",
        )

    await redis.delete(f"email_verify:{body.token}")

    logger.info("Email verified successfully", extra={"user_id": user_id})

    return {"detail": "Email verified successfully."}
