from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from uuid import UUID

class ToolConfig(BaseModel):
    """Configuração de uma ferramenta"""
    id: UUID
    envs: Dict[str, str] = Field(default_factory=dict, description="Variáveis de ambiente da ferramenta")

    class Config:
        from_attributes = True

class MCPServerConfig(BaseModel):
    """Configuração de um servidor MCP"""
    id: UUID
    envs: Dict[str, str] = Field(default_factory=dict, description="Variáveis de ambiente do servidor")

    class Config:
        from_attributes = True

class HTTPToolParameter(BaseModel):
    """Parâmetro de uma ferramenta HTTP"""
    type: str
    required: bool
    description: str

    class Config:
        from_attributes = True

class HTTPToolParameters(BaseModel):
    """Parâmetros de uma ferramenta HTTP"""
    path_params: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Union[str, List[str]]]] = None
    body_params: Optional[Dict[str, HTTPToolParameter]] = None

    class Config:
        from_attributes = True

class HTTPToolErrorHandling(BaseModel):
    """Configuração de tratamento de erros"""
    timeout: int
    retry_count: int
    fallback_response: Dict[str, str]

    class Config:
        from_attributes = True

class HTTPTool(BaseModel):
    """Configuração de uma ferramenta HTTP"""
    name: str
    method: str
    values: Dict[str, str]
    headers: Dict[str, str]
    endpoint: str
    parameters: HTTPToolParameters
    description: str
    error_handling: HTTPToolErrorHandling

    class Config:
        from_attributes = True

class CustomTools(BaseModel):
    """Configuração de ferramentas personalizadas"""
    http_tools: List[HTTPTool] = Field(default_factory=list, description="Lista de ferramentas HTTP")

    class Config:
        from_attributes = True

class LLMConfig(BaseModel):
    """Configuração para agentes do tipo LLM"""
    tools: Optional[List[ToolConfig]] = Field(default=None, description="Lista de ferramentas disponíveis")
    custom_tools: Optional[CustomTools] = Field(default=None, description="Ferramentas personalizadas")
    mcp_servers: Optional[List[MCPServerConfig]] = Field(default=None, description="Lista de servidores MCP")
    sub_agents: Optional[List[UUID]] = Field(default=None, description="Lista de IDs dos sub-agentes")

    class Config:
        from_attributes = True

class SequentialConfig(BaseModel):
    """Configuração para agentes do tipo Sequential"""
    sub_agents: List[UUID] = Field(..., description="Lista de IDs dos sub-agentes em ordem de execução")

    class Config:
        from_attributes = True

class ParallelConfig(BaseModel):
    """Configuração para agentes do tipo Parallel"""
    sub_agents: List[UUID] = Field(..., description="Lista de IDs dos sub-agentes para execução paralela")

    class Config:
        from_attributes = True

class LoopConfig(BaseModel):
    """Configuração para agentes do tipo Loop"""
    sub_agents: List[UUID] = Field(..., description="Lista de IDs dos sub-agentes para execução em loop")
    max_iterations: Optional[int] = Field(default=None, description="Número máximo de iterações")
    condition: Optional[str] = Field(default=None, description="Condição para parar o loop")

    class Config:
        from_attributes = True 