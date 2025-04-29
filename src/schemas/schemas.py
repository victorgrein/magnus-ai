from pydantic import BaseModel, Field, validator, EmailStr
from typing import Optional, Dict, Any, Union, List
from datetime import datetime
from uuid import UUID
import uuid
import re
from src.schemas.agent_config import LLMConfig


class ClientBase(BaseModel):
    name: str
    email: Optional[str] = None

    @validator("email")
    def validate_email(cls, v):
        if v is None:
            return v
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format")
        return v


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
    name: str = Field(..., description="Agent name (no spaces or special characters)")
    description: Optional[str] = Field(None, description="Agent description")
    type: str = Field(..., description="Agent type (llm, sequential, parallel, loop)")
    model: Optional[str] = Field(
        None, description="Agent model (required only for llm type)"
    )
    api_key: Optional[str] = Field(
        None, description="Agent API Key (required only for llm type)"
    )
    instruction: Optional[str] = None
    config: Union[LLMConfig, Dict[str, Any]] = Field(
        ..., description="Agent configuration based on type"
    )

    @validator("name")
    def validate_name(cls, v):
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Agent name cannot contain spaces or special characters")
        return v

    @validator("type")
    def validate_type(cls, v):
        if v not in ["llm", "sequential", "parallel", "loop"]:
            raise ValueError(
                "Invalid agent type. Must be: llm, sequential, parallel or loop"
            )
        return v

    @validator("model")
    def validate_model(cls, v, values):
        if "type" in values and values["type"] == "llm" and not v:
            raise ValueError("Model is required for llm type agents")
        return v

    @validator("api_key")
    def validate_api_key(cls, v, values):
        if "type" in values and values["type"] == "llm" and not v:
            raise ValueError("API Key is required for llm type agents")
        return v

    @validator("config")
    def validate_config(cls, v, values):
        if "type" not in values:
            return v

        if values["type"] == "llm":
            if isinstance(v, dict):
                try:
                    # Convert the dictionary to LLMConfig
                    v = LLMConfig(**v)
                except Exception as e:
                    raise ValueError(f"Invalid LLM configuration for agent: {str(e)}")
            elif not isinstance(v, LLMConfig):
                raise ValueError("Invalid LLM configuration for agent")
        elif values["type"] in ["sequential", "parallel", "loop"]:
            if not isinstance(v, dict):
                raise ValueError(f'Invalid configuration for agent {values["type"]}')
            if "sub_agents" not in v:
                raise ValueError(f'Agent {values["type"]} must have sub_agents')
            if not isinstance(v["sub_agents"], list):
                raise ValueError("sub_agents must be a list")
            if not v["sub_agents"]:
                raise ValueError(
                    f'Agent {values["type"]} must have at least one sub-agent'
                )
        return v


class AgentCreate(AgentBase):
    client_id: UUID


class Agent(AgentBase):
    id: UUID
    client_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    agent_card_url: Optional[str] = None

    class Config:
        from_attributes = True


class ToolConfig(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    inputModes: List[str] = Field(default_factory=list)
    outputModes: List[str] = Field(default_factory=list)


class MCPServerBase(BaseModel):
    name: str
    description: Optional[str] = None
    config_json: Dict[str, Any] = Field(default_factory=dict)
    environments: Dict[str, Any] = Field(default_factory=dict)
    tools: List[ToolConfig] = Field(default_factory=list)
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
