from datetime import datetime
from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field


class MessagePart(BaseModel):
    type: str
    text: str


class Message(BaseModel):
    role: str
    parts: List[MessagePart]


class TaskStatusUpdateEvent(BaseModel):
    state: str = Field(..., description="Estado da tarefa (working, completed, failed)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: Optional[Message] = None
    error: Optional[Dict[str, Any]] = None


class TaskArtifactUpdateEvent(BaseModel):
    type: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    method: Literal["tasks/sendSubscribe"] = "tasks/sendSubscribe"
    params: Dict[str, Any]


class JSONRPCResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
