from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    name: str  # Para criação do cliente associado

class AdminUserCreate(UserBase):
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: UUID
    client_id: Optional[UUID] = None
    is_active: bool
    email_verified: bool
    is_admin: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    
class TokenData(BaseModel):
    sub: str  # email do usuário
    exp: datetime
    is_admin: bool
    client_id: Optional[UUID] = None
    
class PasswordReset(BaseModel):
    token: str
    new_password: str
    
class ForgotPassword(BaseModel):
    email: EmailStr

class MessageResponse(BaseModel):
    message: str 