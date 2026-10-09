import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base user properties shared across request schemas."""
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password must be between 8 and 128 characters.",
    )


class UserLogin(BaseModel):
    """Schema for JSON-based login request."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(UserBase):
    """Public user response schema excluding sensitive credentials."""
    id: uuid.UUID
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """OAuth2 / JWT response token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """Decoded JWT payload data."""
    sub: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
