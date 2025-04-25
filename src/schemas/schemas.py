from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class ClientBase(BaseModel):
    name: str

class ClientCreate(ClientBase):
    pass

class Client(ClientBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class ContactBase(BaseModel):
    ext_id: Optional[str] = None
    name: Optional[str] = None
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ContactCreate(ContactBase):
    client_id: UUID

class Contact(ContactBase):
    id: UUID
    client_id: UUID

    class Config:
        from_attributes = True

class AgentBase(BaseModel):
    name: str
    type: str = Field(..., pattern="^(llm|sequential|parallel|loop)$")
    model: str
    api_key: str
    instruction: Optional[str] = None
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class AgentCreate(AgentBase):
    client_id: UUID

class Agent(AgentBase):
    id: UUID
    client_id: UUID

    class Config:
        from_attributes = True