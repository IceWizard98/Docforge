from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str


class LoginResponse(BaseModel):
    token: str
    refresh_token: str = ""
    user: UserResponse
    expires_in: int


class RegisterResponse(BaseModel):
    user: UserResponse
    token: str = ""


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8)


class VerifyEmailRequest(BaseModel):
    token: str


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
