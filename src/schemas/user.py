from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
import uuid


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User password")
    name: str = Field(..., description="User's name")


class AdminUserCreate(UserBase):
    password: str
    name: str


class UserLogin(UserBase):
    password: str


class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    is_admin: bool
    client_id: Optional[uuid.UUID] = None
    email_verified: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[uuid.UUID] = None
    sub: Optional[str] = None
    is_admin: bool
    client_id: Optional[uuid.UUID] = None
    exp: datetime


class PasswordReset(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, description="New password")


class ForgotPassword(BaseModel):
    email: EmailStr


class ChangePassword(BaseModel):
    current_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(..., min_length=8, description="New password to set")


class MessageResponse(BaseModel):
    message: str
