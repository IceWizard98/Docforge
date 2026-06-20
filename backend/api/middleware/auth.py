from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from adapters.redis.client import RedisClient
from config.settings import get_settings


class AuthUser(BaseModel):
    user_id: str
    role: str
    email: str | None = None


security = HTTPBearer(auto_error=False)


async def blacklist_token(token: str, ttl: int = 3600) -> None:
    redis = await RedisClient.get_client()
    if redis is None:
        return
    payload = jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=[get_settings().jwt_algorithm],
        options={"verify_exp": False},
    )
    jti = payload.get("jti", token)
    await redis.sadd("token_blacklist", jti)
    await redis.expire("token_blacklist", ttl)


async def blacklist_user_tokens(user_id: str, ttl: int = 3600) -> None:
    redis = await RedisClient.get_client()
    if redis is None:
        return
    key = f"user:{user_id}:tokens"
    members = await redis.smembers(key)
    if members:
        for jti in members:
            await redis.sadd("token_blacklist", jti)
        await redis.expire("token_blacklist", ttl)
    await redis.delete(key)


async def _decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[get_settings().jwt_algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    redis = await RedisClient.get_client()
    if redis is not None:
        jti = payload.get("jti", token)
        if await redis.sismember("token_blacklist", jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return payload


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> AuthUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = await _decode_token(token)
    user_id = payload.get("sub")
    role = payload.get("role")
    email = payload.get("email")
    token_type = payload.get("token_type")
    if user_id is None or role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for this endpoint",
        )
    request.state.user = payload
    return AuthUser(
        user_id=str(user_id),
        role=str(role),
        email=str(email) if email else None,
    )


def require_role(required_role: str):
    def role_checker(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if current_user.role not in (required_role, "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return current_user
    return role_checker
