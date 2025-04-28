from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, Union, List
from datetime import datetime
from uuid import UUID
import uuid
import re
from .agent_config import LLMConfig, SequentialConfig, ParallelConfig, LoopConfig

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
    name: str = Field(..., description="Nome do agente (sem espaços ou caracteres especiais)")
    description: Optional[str] = Field(None, description="Descrição do agente")
    type: str = Field(..., description="Tipo do agente (llm, sequential, parallel, loop)")
    model: Optional[str] = Field(None, description="Modelo do agente (obrigatório apenas para tipo llm)")
    api_key: Optional[str] = Field(None, description="API Key do agente (obrigatória apenas para tipo llm)")
    instruction: Optional[str] = None
    config: Union[LLMConfig, Dict[str, Any]] = Field(..., description="Configuração do agente baseada no tipo")

    @validator('name')
    def validate_name(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('O nome do agente não pode conter espaços ou caracteres especiais')
        return v

    @validator('type')
    def validate_type(cls, v):
        if v not in ['llm', 'sequential', 'parallel', 'loop']:
            raise ValueError('Tipo de agente inválido. Deve ser: llm, sequential, parallel ou loop')
        return v

    @validator('model')
    def validate_model(cls, v, values):
        if 'type' in values and values['type'] == 'llm' and not v:
            raise ValueError('Modelo é obrigatório para agentes do tipo llm')
        return v

    @validator('api_key')
    def validate_api_key(cls, v, values):
        if 'type' in values and values['type'] == 'llm' and not v:
            raise ValueError('API Key é obrigatória para agentes do tipo llm')
        return v

    @validator('config')
    def validate_config(cls, v, values):
        if 'type' not in values:
            return v
            
        if values['type'] == 'llm':
            if isinstance(v, dict):
                try:
                    # Converte o dicionário para LLMConfig
                    v = LLMConfig(**v)
                except Exception as e:
                    raise ValueError(f'Configuração inválida para agente LLM: {str(e)}')
            elif not isinstance(v, LLMConfig):
                raise ValueError('Configuração inválida para agente LLM')
        elif values['type'] in ['sequential', 'parallel', 'loop']:
            if not isinstance(v, dict):
                raise ValueError(f'Configuração inválida para agente {values["type"]}')
            if 'sub_agents' not in v:
                raise ValueError(f'Agente {values["type"]} deve ter sub_agents')
            if not isinstance(v['sub_agents'], list):
                raise ValueError('sub_agents deve ser uma lista')
            if not v['sub_agents']:
                raise ValueError(f'Agente {values["type"]} deve ter pelo menos um sub-agente')
        return v

class AgentCreate(AgentBase):
    client_id: UUID

class Agent(AgentBase):
    id: UUID
    client_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class MCPServerBase(BaseModel):
    name: str
    description: Optional[str] = None
    config_json: Dict[str, Any] = Field(default_factory=dict)
    environments: Dict[str, Any] = Field(default_factory=dict)
    type: str = Field(default="official")

class MCPServerCreate(MCPServerBase):
    pass

class MCPServer(MCPServerBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ToolBase(BaseModel):
    name: str
    description: Optional[str] = None
    config_json: Dict[str, Any] = Field(default_factory=dict)
    environments: Dict[str, Any] = Field(default_factory=dict)

class ToolCreate(ToolBase):
    pass

class Tool(ToolBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True