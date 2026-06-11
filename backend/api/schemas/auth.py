from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str
    tenant_slug: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str
    tenant_slug: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    status: str


class LoginResponse(BaseModel):
    token: str
    user: UserResponse
    expires_in: int


class RegisterResponse(BaseModel):
    user: UserResponse
    tenant: TenantResponse
    token: str = ""
