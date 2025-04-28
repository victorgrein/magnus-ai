from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class AuditLogBase(BaseModel):
    """Base schema for audit log"""
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class AuditLogCreate(AuditLogBase):
    """Schema for creating audit log"""
    pass

class AuditLogResponse(AuditLogBase):
    """Schema for audit log response"""
    id: UUID
    user_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class AuditLogFilter(BaseModel):
    """Schema for audit log search filters"""
    user_id: Optional[UUID] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    skip: Optional[int] = Field(0, ge=0)
    limit: Optional[int] = Field(100, ge=1, le=1000) 