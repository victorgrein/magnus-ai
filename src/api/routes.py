from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import uuid
from datetime import datetime

from src.config.database import get_db
from src.core.jwt_middleware import get_jwt_token, verify_user_client, verify_admin, get_current_user_client_id
from src.schemas.schemas import (
    Client,
    ClientCreate,
    Contact,
    ContactCreate,
    Agent,
    AgentCreate,
    MCPServer,
    MCPServerCreate,
    Tool,
    ToolCreate,
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
from google.adk.events import Event
from google.adk.sessions import Session as Adk_Session
from src.config.settings import settings
from src.services.session_service import (
    get_session_events,
    get_session_by_id,
    delete_session,
    get_sessions_by_agent,
    get_sessions_by_client,
)

router = APIRouter()

# Configuração do PostgreSQL
POSTGRES_CONNECTION_STRING = settings.POSTGRES_CONNECTION_STRING

# Inicializar os serviços globalmente
session_service = DatabaseSessionService(db_url=POSTGRES_CONNECTION_STRING)
artifacts_service = InMemoryArtifactService()
memory_service = InMemoryMemoryService()


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verificar se o agente pertence ao cliente do usuário
    agent = agent_service.get_agent(db, request.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Agente não encontrado"
        )
    
    # Verificar se o usuário tem acesso ao agente (via cliente)
    await verify_user_client(payload, db, agent.client_id)
    
    try:
        final_response_text = await run_agent(
            request.agent_id,
            request.contact_id,
            request.message,
            session_service,
            artifacts_service,
            memory_service,
            db,
        )

        return {
            "response": final_response_text,
            "status": "success",
            "timestamp": datetime.now().isoformat(),
        }

    except AgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# Rotas para Sessões
@router.get("/sessions/client/{client_id}", response_model=List[Adk_Session])
async def get_client_sessions(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verificar se o usuário tem acesso aos dados deste cliente
    await verify_user_client(payload, db, client_id)
    return get_sessions_by_client(db, client_id)


@router.get("/sessions/agent/{agent_id}", response_model=List[Adk_Session])
async def get_agent_sessions(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
    skip: int = 0,
    limit: int = 100,
):
    # Verificar se o agente pertence ao cliente do usuário
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Agente não encontrado"
        )
    
    # Verificar se o usuário tem acesso ao agente (via cliente)
    await verify_user_client(payload, db, agent.client_id)
    
    return get_sessions_by_agent(db, agent_id, skip, limit)


@router.get("/sessions/{session_id}", response_model=Adk_Session)
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Obter a sessão
    session = get_session_by_id(session_service, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Sessão não encontrada"
        )
    
    # Verificar se o agente da sessão pertence ao cliente do usuário
    agent_id = uuid.UUID(session.agent_id) if session.agent_id else None
    if agent_id:
        agent = agent_service.get_agent(db, agent_id)
        if agent:
            await verify_user_client(payload, db, agent.client_id)
    
    return session


@router.get(
    "/sessions/{session_id}/messages",
    response_model=List[Event],
)
async def get_agent_messages(
    session_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Obter a sessão
    session = get_session_by_id(session_service, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Sessão não encontrada"
        )
    
    # Verificar se o agente da sessão pertence ao cliente do usuário
    agent_id = uuid.UUID(session.agent_id) if session.agent_id else None
    if agent_id:
        agent = agent_service.get_agent(db, agent_id)
        if agent:
            await verify_user_client(payload, db, agent.client_id)
    
    return get_session_events(session_service, session_id)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_session(
    session_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Obter a sessão
    session = get_session_by_id(session_service, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Sessão não encontrada"
        )
    
    # Verificar se o agente da sessão pertence ao cliente do usuário
    agent_id = uuid.UUID(session.agent_id) if session.agent_id else None
    if agent_id:
        agent = agent_service.get_agent(db, agent_id)
        if agent:
            await verify_user_client(payload, db, agent.client_id)
    
    return delete_session(session_service, session_id)


# Rotas para Clientes
@router.post("/clients/", response_model=Client, status_code=status.HTTP_201_CREATED)
async def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Apenas administradores podem criar clientes
    await verify_admin(payload)
    return client_service.create_client(db, client)


@router.get("/clients/", response_model=List[Client])
async def read_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Se for administrador, pode ver todos os clientes
    # Se for usuário comum, só vê o próprio cliente
    client_id = get_current_user_client_id(payload)
    
    if client_id:
        # Usuário comum - retorna apenas seu próprio cliente
        client = client_service.get_client(db, client_id)
        return [client] if client else []
    else:
        # Administrador - retorna todos os clientes
        return client_service.get_clients(db, skip, limit)


@router.get("/clients/{client_id}", response_model=Client)
async def read_client(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verificar se o usuário tem acesso aos dados deste cliente
    await verify_user_client(payload, db, client_id)
    
    db_client = client_service.get_client(db, client_id)
    if db_client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado"
        )
    return db_client


@router.put("/clients/{client_id}", response_model=Client)
async def update_client(
    client_id: uuid.UUID,
    client: ClientCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verificar se o usuário tem acesso aos dados deste cliente
    await verify_user_client(payload, db, client_id)
    
    db_client = client_service.update_client(db, client_id, client)
    if db_client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado"
        )
    return db_client


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Apenas administradores podem excluir clientes
    await verify_admin(payload)
    
    if not client_service.delete_client(db, client_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado"
        )


# Rotas para Contatos
@router.post("/contacts/", response_model=Contact, status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact: ContactCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verificar se o usuário tem acesso ao cliente do contato
    await verify_user_client(payload, db, contact.client_id)
    
    return contact_service.create_contact(db, contact)


@router.get("/contacts/{client_id}", response_model=List[Contact])
async def read_contacts(
    client_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verificar se o usuário tem acesso aos dados deste cliente
    await verify_user_client(payload, db, client_id)
    
    return contact_service.get_contacts_by_client(db, client_id, skip, limit)


@router.get("/contact/{contact_id}", response_model=Contact)
async def read_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    db_contact = contact_service.get_contact(db, contact_id)
    if db_contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contato não encontrado"
        )
    
    # Verificar se o usuário tem acesso ao cliente do contato
    await verify_user_client(payload, db, db_contact.client_id)
    
    return db_contact


@router.put("/contact/{contact_id}", response_model=Contact)
async def update_contact(
    contact_id: uuid.UUID,
    contact: ContactCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Buscar o contato atual
    db_current_contact = contact_service.get_contact(db, contact_id)
    if db_current_contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contato não encontrado"
        )
    
    # Verificar se o usuário tem acesso ao cliente do contato
    await verify_user_client(payload, db, db_current_contact.client_id)
    
    # Verificar se está tentando mudar o cliente
    if contact.client_id != db_current_contact.client_id:
        # Verificar se o usuário tem acesso ao novo cliente também
        await verify_user_client(payload, db, contact.client_id)
    
    db_contact = contact_service.update_contact(db, contact_id, contact)
    if db_contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contato não encontrado"
        )
    return db_contact


@router.delete("/contact/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Buscar o contato
    db_contact = contact_service.get_contact(db, contact_id)
    if db_contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contato não encontrado"
        )
    
    # Verificar se o usuário tem acesso ao cliente do contato
    await verify_user_client(payload, db, db_contact.client_id)
    
    if not contact_service.delete_contact(db, contact_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contato não encontrado"
        )


# Rotas para Agentes
@router.post("/agents/", response_model=Agent, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent: AgentCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verificar se o usuário tem acesso ao cliente do agente
    await verify_user_client(payload, db, agent.client_id)
    
    return agent_service.create_agent(db, agent)


@router.get("/agents/{client_id}", response_model=List[Agent])
async def read_agents(
    client_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verificar se o usuário tem acesso aos dados deste cliente
    await verify_user_client(payload, db, client_id)
    
    return agent_service.get_agents_by_client(db, client_id, skip, limit)


@router.get("/agent/{agent_id}", response_model=Agent)
async def read_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    db_agent = agent_service.get_agent(db, agent_id)
    if db_agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado"
        )
    
    # Verificar se o usuário tem acesso ao cliente do agente
    await verify_user_client(payload, db, db_agent.client_id)
    
    return db_agent


@router.put("/agent/{agent_id}", response_model=Agent)
async def update_agent(
    agent_id: uuid.UUID, 
    agent_data: Dict[str, Any],
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Buscar o agente atual
    db_agent = agent_service.get_agent(db, agent_id)
    if db_agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado"
        )
    
    # Verificar se o usuário tem acesso ao cliente do agente
    await verify_user_client(payload, db, db_agent.client_id)
    
    # Se estiver tentando mudar o client_id, verificar permissão para o novo cliente também
    if 'client_id' in agent_data and agent_data['client_id'] != str(db_agent.client_id):
        new_client_id = uuid.UUID(agent_data['client_id'])
        await verify_user_client(payload, db, new_client_id)
    
    return await agent_service.update_agent(db, agent_id, agent_data)


@router.delete("/agent/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Buscar o agente
    db_agent = agent_service.get_agent(db, agent_id)
    if db_agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado"
        )
    
    # Verificar se o usuário tem acesso ao cliente do agente
    await verify_user_client(payload, db, db_agent.client_id)
    
    if not agent_service.delete_agent(db, agent_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado"
        )


# Rotas para Servidores MCP
@router.post(
    "/mcp-servers/", response_model=MCPServer, status_code=status.HTTP_201_CREATED
)
async def create_mcp_server(
    server: MCPServerCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Apenas administradores podem criar servidores MCP
    await verify_admin(payload)
    
    return mcp_server_service.create_mcp_server(db, server)


@router.get("/mcp-servers/", response_model=List[MCPServer])
async def read_mcp_servers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Todos os usuários autenticados podem listar servidores MCP
    return mcp_server_service.get_mcp_servers(db, skip, limit)


@router.get("/mcp-servers/{server_id}", response_model=MCPServer)
async def read_mcp_server(
    server_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Todos os usuários autenticados podem ver detalhes do servidor MCP
    db_server = mcp_server_service.get_mcp_server(db, server_id)
    if db_server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Servidor MCP não encontrado"
        )
    return db_server


@router.put("/mcp-servers/{server_id}", response_model=MCPServer)
async def update_mcp_server(
    server_id: uuid.UUID,
    server: MCPServerCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Apenas administradores podem atualizar servidores MCP
    await verify_admin(payload)
    
    db_server = mcp_server_service.update_mcp_server(db, server_id, server)
    if db_server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Servidor MCP não encontrado"
        )
    return db_server


@router.delete("/mcp-servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server(
    server_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Apenas administradores podem excluir servidores MCP
    await verify_admin(payload)
    
    if not mcp_server_service.delete_mcp_server(db, server_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Servidor MCP não encontrado"
        )


# Rotas para Ferramentas
@router.post("/tools/", response_model=Tool, status_code=status.HTTP_201_CREATED)
async def create_tool(
    tool: ToolCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Apenas administradores podem criar ferramentas
    await verify_admin(payload)
    
    return tool_service.create_tool(db, tool)


@router.get("/tools/", response_model=List[Tool])
async def read_tools(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Todos os usuários autenticados podem listar ferramentas
    return tool_service.get_tools(db, skip, limit)


@router.get("/tools/{tool_id}", response_model=Tool)
async def read_tool(
    tool_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Todos os usuários autenticados podem ver detalhes da ferramenta
    db_tool = tool_service.get_tool(db, tool_id)
    if db_tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ferramenta não encontrada"
        )
    return db_tool


@router.put("/tools/{tool_id}", response_model=Tool)
async def update_tool(
    tool_id: uuid.UUID,
    tool: ToolCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Apenas administradores podem atualizar ferramentas
    await verify_admin(payload)
    
    db_tool = tool_service.update_tool(db, tool_id, tool)
    if db_tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ferramenta não encontrada"
        )
    return db_tool


@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Apenas administradores podem excluir ferramentas
    await verify_admin(payload)
    
    if not tool_service.delete_tool(db, tool_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ferramenta não encontrada"
        )
