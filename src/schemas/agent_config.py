from typing import List, Optional, Dict, Union, Any
from pydantic import BaseModel, Field
from uuid import UUID
import secrets
import string


class ToolConfig(BaseModel):
    """Configuration of a tool"""

    id: UUID
    envs: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables of the tool"
    )

    class Config:
        from_attributes = True


class MCPServerConfig(BaseModel):
    """Configuration of an MCP server"""

    id: UUID
    envs: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables of the server"
    )
    tools: List[str] = Field(
        default_factory=list, description="List of tools of the server"
    )

    class Config:
        from_attributes = True


class CustomMCPServerConfig(BaseModel):
    """Configuration of a custom MCP server"""

    url: str = Field(..., description="Server URL of the custom MCP server")
    headers: Dict[str, str] = Field(
        default_factory=dict, description="Headers for requests to the server"
    )

    class Config:
        from_attributes = True


class FlowNodes(BaseModel):
    """Configuration of workflow nodes"""

    nodes: List[Any]
    edges: List[Any]


class HTTPToolParameter(BaseModel):
    """Parameter of an HTTP tool"""

    type: str
    required: bool
    description: str

    class Config:
        from_attributes = True


class HTTPToolParameters(BaseModel):
    """Parameters of an HTTP tool"""

    path_params: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Union[str, List[str]]]] = None
    body_params: Optional[Dict[str, HTTPToolParameter]] = None

    class Config:
        from_attributes = True


class HTTPToolErrorHandling(BaseModel):
    """Configuration of error handling"""

    timeout: int
    retry_count: int
    fallback_response: Dict[str, str]

    class Config:
        from_attributes = True


class HTTPTool(BaseModel):
    """Configuration of an HTTP tool"""

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
    """Configuration of custom tools"""

    http_tools: List[HTTPTool] = Field(
        default_factory=list, description="List of HTTP tools"
    )

    class Config:
        from_attributes = True


def generate_api_key(length: int = 32) -> str:
    """Generate a secure API key."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class LLMConfig(BaseModel):
    """Configuration for LLM agents"""

    api_key: str = Field(
        default_factory=generate_api_key,
        description="API key for the LLM. If not provided, a secure key will be generated automatically.",
    )

    tools: Optional[List[ToolConfig]] = Field(
        default=None, description="List of available tools"
    )
    custom_tools: Optional[CustomTools] = Field(
        default=None, description="Custom tools"
    )
    mcp_servers: Optional[List[MCPServerConfig]] = Field(
        default=None, description="List of MCP servers"
    )
    custom_mcp_servers: Optional[List[CustomMCPServerConfig]] = Field(
        default=None, description="List of custom MCP servers with URL and headers"
    )
    agent_tools: Optional[List[UUID]] = Field(
        default=None, description="List of IDs of sub-agents"
    )
    sub_agents: Optional[List[UUID]] = Field(
        default=None, description="List of IDs of sub-agents"
    )
    workflow: Optional[FlowNodes] = Field(
        default=None, description="Workflow configuration"
    )

    class Config:
        from_attributes = True


class SequentialConfig(BaseModel):
    """Configuration for sequential agents"""

    sub_agents: List[UUID] = Field(
        ..., description="List of IDs of sub-agents in execution order"
    )

    class Config:
        from_attributes = True


class ParallelConfig(BaseModel):
    """Configuration for parallel agents"""

    sub_agents: List[UUID] = Field(
        ..., description="List of IDs of sub-agents for parallel execution"
    )

    class Config:
        from_attributes = True


class LoopConfig(BaseModel):
    """Configuration for loop agents"""

    sub_agents: List[UUID] = Field(
        ..., description="List of IDs of sub-agents for loop execution"
    )
    max_iterations: Optional[int] = Field(
        default=None, description="Maximum number of iterations"
    )
    condition: Optional[str] = Field(
        default=None, description="Condition to stop the loop"
    )

    class Config:
        from_attributes = True


class WorkflowConfig(BaseModel):
    """Configuration for workflow agents"""

    workflow: Dict[str, Any] = Field(
        ..., description="Workflow configuration with nodes and edges"
    )
    sub_agents: Optional[List[UUID]] = Field(
        default_factory=list, description="List of IDs of sub-agents used in workflow"
    )
    api_key: Optional[str] = Field(
        default_factory=generate_api_key, description="API key for the workflow agent"
    )

    class Config:
        from_attributes = True
