from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class ChatRequest(BaseModel):
    """Schema for chat requests"""

    agent_id: str = Field(
        ..., description="ID of the agent that will process the message"
    )
    contact_id: str = Field(
        ..., description="ID of the contact that will process the message"
    )
    message: str = Field(..., description="User message")


class ChatResponse(BaseModel):
    """Schema for chat responses"""

    response: str = Field(..., description="Agent response")
    status: str = Field(..., description="Operation status")
    error: Optional[str] = Field(None, description="Error message, if there is one")
    timestamp: str = Field(..., description="Timestamp of the response")


class ErrorResponse(BaseModel):
    """Schema for error responses"""

    error: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code of the error")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
