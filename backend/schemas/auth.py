from pydantic import BaseModel, EmailStr, SecretStr, Field
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: SecretStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(..., min_length=8)
    display_name: Optional[str] = Field(None, max_length=255)


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    role: str
    plan: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse