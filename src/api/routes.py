from fastapi import APIRouter, Depends, HTTPException, status, Security
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import uuid
from datetime import datetime

from src.config.database import get_db
from src.core.middleware import get_api_key
from src.schemas.schemas import (
    Client, ClientCreate,
    Contact, ContactCreate,
    Agent, AgentCreate,
    MCPServer, MCPServerCreate,
    Tool, ToolCreate,
)
from src.services import (
    client_service,
    contact_service,
    agent_service,
    mcp_server_service,
    tool_service,
)
from src.schemas.chat import ChatRequest, ChatResponse, ErrorResponse
from src.services.agent_runner import run_agent
from src.core.exceptions import AgentNotFoundError
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.sessions import DatabaseSessionService
from google.adk.memory import InMemoryMemoryService
from src.config.settings import settings

router = APIRouter()

# Configuração do PostgreSQL
POSTGRES_CONNECTION_STRING = settings.POSTGRES_CONNECTION_STRING

# Inicializar os serviços globalmente
session_service = DatabaseSessionService(db_url=POSTGRES_CONNECTION_STRING)
artifacts_service = InMemoryArtifactService()
memory_service = InMemoryMemoryService()

@router.post("/chat", response_model=ChatResponse, responses={
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
async def chat(
    request: ChatRequest, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    try:
        final_response_text = await run_agent(
            request.agent_id, 
            request.contact_id,
            request.message, 
            session_service, 
            artifacts_service,
            memory_service,
            db
        )
        
        return {
            "response": final_response_text,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }

    except AgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# Rotas para Clientes
@router.post("/clients/", response_model=Client, status_code=status.HTTP_201_CREATED)
def create_client(
    client: ClientCreate, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    return client_service.create_client(db, client)

@router.get("/clients/", response_model=List[Client])
def read_clients(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    return client_service.get_clients(db, skip, limit)

@router.get("/clients/{client_id}", response_model=Client)
def read_client(
    client_id: uuid.UUID, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    db_client = client_service.get_client(db, client_id)
    if db_client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return db_client

@router.put("/clients/{client_id}", response_model=Client)
def update_client(
    client_id: uuid.UUID, 
    client: ClientCreate, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    db_client = client_service.update_client(db, client_id, client)
    if db_client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return db_client

@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: uuid.UUID, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    if not client_service.delete_client(db, client_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")

# Rotas para Contatos
@router.post("/contacts/", response_model=Contact, status_code=status.HTTP_201_CREATED)
def create_contact(
    contact: ContactCreate, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    return contact_service.create_contact(db, contact)

@router.get("/contacts/{client_id}", response_model=List[Contact])
def read_contacts(
    client_id: uuid.UUID, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    return contact_service.get_contacts_by_client(db, client_id, skip, limit)

@router.get("/contact/{contact_id}", response_model=Contact)
def read_contact(
    contact_id: uuid.UUID, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    db_contact = contact_service.get_contact(db, contact_id)
    if db_contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contato não encontrado")
    return db_contact

@router.put("/contact/{contact_id}", response_model=Contact)
def update_contact(
    contact_id: uuid.UUID, 
    contact: ContactCreate, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    db_contact = contact_service.update_contact(db, contact_id, contact)
    if db_contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contato não encontrado")
    return db_contact

@router.delete("/contact/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: uuid.UUID, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    if not contact_service.delete_contact(db, contact_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contato não encontrado")

# Rotas para Agentes
@router.post("/agents/", response_model=Agent, status_code=status.HTTP_201_CREATED)
def create_agent(
    agent: AgentCreate, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    return agent_service.create_agent(db, agent)

@router.get("/agents/{client_id}", response_model=List[Agent])
def read_agents(
    client_id: uuid.UUID, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    return agent_service.get_agents_by_client(db, client_id, skip, limit)

@router.get("/agent/{agent_id}", response_model=Agent)
def read_agent(
    agent_id: uuid.UUID, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    db_agent = agent_service.get_agent(db, agent_id)
    if db_agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado")
    return db_agent

@router.put("/agent/{agent_id}", response_model=Agent)
async def update_agent(
    agent_id: uuid.UUID,
    agent_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Atualiza um agente existente"""
    return await agent_service.update_agent(db, agent_id, agent_data)

@router.delete("/agent/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: uuid.UUID, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    if not agent_service.delete_agent(db, agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado")

# Rotas para MCPServers
@router.post("/mcp-servers/", response_model=MCPServer, status_code=status.HTTP_201_CREATED)
def create_mcp_server(
    server: MCPServerCreate, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    return mcp_server_service.create_mcp_server(db, server)

@router.get("/mcp-servers/", response_model=List[MCPServer])
def read_mcp_servers(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    return mcp_server_service.get_mcp_servers(db, skip, limit)

@router.get("/mcp-servers/{server_id}", response_model=MCPServer)
def read_mcp_server(
    server_id: uuid.UUID, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    db_server = mcp_server_service.get_mcp_server(db, server_id)
    if db_server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor MCP não encontrado")
    return db_server

@router.put("/mcp-servers/{server_id}", response_model=MCPServer)
def update_mcp_server(
    server_id: uuid.UUID, 
    server: MCPServerCreate, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    db_server = mcp_server_service.update_mcp_server(db, server_id, server)
    if db_server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor MCP não encontrado")
    return db_server

@router.delete("/mcp-servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mcp_server(
    server_id: uuid.UUID, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    if not mcp_server_service.delete_mcp_server(db, server_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servidor MCP não encontrado")

# Rotas para Tools
@router.post("/tools/", response_model=Tool, status_code=status.HTTP_201_CREATED)
def create_tool(
    tool: ToolCreate, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    return tool_service.create_tool(db, tool)

@router.get("/tools/", response_model=List[Tool])
def read_tools(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    return tool_service.get_tools(db, skip, limit)

@router.get("/tools/{tool_id}", response_model=Tool)
def read_tool(
    tool_id: uuid.UUID, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    db_tool = tool_service.get_tool(db, tool_id)
    if db_tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ferramenta não encontrada")
    return db_tool

@router.put("/tools/{tool_id}", response_model=Tool)
def update_tool(
    tool_id: uuid.UUID, 
    tool: ToolCreate, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    db_tool = tool_service.update_tool(db, tool_id, tool)
    if db_tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ferramenta não encontrada")
    return db_tool

@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tool(
    tool_id: uuid.UUID, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    if not tool_service.delete_tool(db, tool_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ferramenta não encontrada")