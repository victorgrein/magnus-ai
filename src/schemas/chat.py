from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class ChatRequest(BaseModel):
    """Schema para requisições de chat"""
    agent_id: str = Field(..., description="ID do agente que irá processar a mensagem")
    contact_id: str = Field(..., description="ID do contato que irá processar a mensagem")
    message: str = Field(..., description="Mensagem do usuário")

class ChatResponse(BaseModel):
    """Schema para respostas do chat"""
    response: str = Field(..., description="Resposta do agente")
    status: str = Field(..., description="Status da operação")
    error: Optional[str] = Field(None, description="Mensagem de erro, se houver")
    timestamp: str = Field(..., description="Timestamp da resposta")

class ErrorResponse(BaseModel):
    """Schema para respostas de erro"""
    error: str = Field(..., description="Mensagem de erro")
    status_code: int = Field(..., description="Código HTTP do erro")
    details: Optional[Dict[str, Any]] = Field(None, description="Detalhes adicionais do erro") 