from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from sqlalchemy.orm import Session
from src.config.database import get_db
from typing import List, Dict, Any, Optional
import uuid
from src.core.jwt_middleware import (
    get_jwt_token,
    verify_user_client,
)
from src.schemas.schemas import (
    Agent,
    AgentCreate,
    AgentFolder,
    AgentFolderCreate,
    AgentFolderUpdate,
)
from src.services import (
    agent_service,
    mcp_server_service,
)
import logging

logger = logging.getLogger(__name__)


async def format_agent_tools(
    mcp_servers: List[Dict[str, Any]], db: Session
) -> List[Dict[str, Any]]:
    """Format MCP server tools for agent card skills"""
    formatted_tools = []

    for server in mcp_servers:
        try:
            # Get the MCP server by ID
            server_id = uuid.UUID(server["id"])
            mcp_server = mcp_server_service.get_mcp_server(db, server_id)

            if not mcp_server:
                logger.warning(f"MCP server not found: {server_id}")
                continue

            # Format each tool
            for tool in mcp_server.tools:
                formatted_tool = {
                    "id": tool["id"],
                    "name": tool["name"],
                    "description": tool["description"],
                    "tags": tool["tags"],
                    "examples": tool["examples"],
                    "inputModes": tool["inputModes"],
                    "outputModes": tool["outputModes"],
                }
                formatted_tools.append(formatted_tool)

        except Exception as e:
            logger.error(
                f"Error formatting tools for MCP server {server.get('id')}: {str(e)}"
            )
            continue

    return formatted_tools


router = APIRouter(
    prefix="/agents",
    tags=["agents"],
    responses={404: {"description": "Not found"}},
)


# Rotas para pastas de agentes
@router.post(
    "/folders", response_model=AgentFolder, status_code=status.HTTP_201_CREATED
)
async def create_folder(
    folder: AgentFolderCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    """Cria uma nova pasta para organizar agentes"""
    # Verifica se o usuário tem acesso ao cliente da pasta
    await verify_user_client(payload, db, folder.client_id)

    return agent_service.create_agent_folder(
        db, folder.client_id, folder.name, folder.description
    )


@router.get("/folders", response_model=List[AgentFolder])
async def read_folders(
    x_client_id: uuid.UUID = Header(..., alias="x-client-id"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    """Lista as pastas de agentes de um cliente"""
    # Verifica se o usuário tem acesso aos dados deste cliente
    await verify_user_client(payload, db, x_client_id)

    return agent_service.get_agent_folders_by_client(db, x_client_id, skip, limit)


@router.get("/folders/{folder_id}", response_model=AgentFolder)
async def read_folder(
    folder_id: uuid.UUID,
    x_client_id: uuid.UUID = Header(..., alias="x-client-id"),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    """Obtém os detalhes de uma pasta específica"""
    # Verifica se o usuário tem acesso aos dados deste cliente
    await verify_user_client(payload, db, x_client_id)

    folder = agent_service.get_agent_folder(db, folder_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pasta não encontrada"
        )

    # Verifica se a pasta pertence ao cliente informado
    if folder.client_id != x_client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pasta não pertence ao cliente informado",
        )

    return folder


@router.put("/folders/{folder_id}", response_model=AgentFolder)
async def update_folder(
    folder_id: uuid.UUID,
    folder_data: AgentFolderUpdate,
    x_client_id: uuid.UUID = Header(..., alias="x-client-id"),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    """Atualiza uma pasta de agentes"""
    # Verifica se o usuário tem acesso aos dados deste cliente
    await verify_user_client(payload, db, x_client_id)

    # Verifica se a pasta existe
    folder = agent_service.get_agent_folder(db, folder_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pasta não encontrada"
        )

    # Verifica se a pasta pertence ao cliente informado
    if folder.client_id != x_client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pasta não pertence ao cliente informado",
        )

    # Atualiza a pasta
    updated_folder = agent_service.update_agent_folder(
        db, folder_id, folder_data.name, folder_data.description
    )
    return updated_folder


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: uuid.UUID,
    x_client_id: uuid.UUID = Header(..., alias="x-client-id"),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    """Remove uma pasta de agentes"""
    # Verifica se o usuário tem acesso aos dados deste cliente
    await verify_user_client(payload, db, x_client_id)

    # Verifica se a pasta existe
    folder = agent_service.get_agent_folder(db, folder_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pasta não encontrada"
        )

    # Verifica se a pasta pertence ao cliente informado
    if folder.client_id != x_client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pasta não pertence ao cliente informado",
        )

    # Deleta a pasta
    if not agent_service.delete_agent_folder(db, folder_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pasta não encontrada"
        )


@router.get("/folders/{folder_id}/agents", response_model=List[Agent])
async def read_folder_agents(
    folder_id: uuid.UUID,
    x_client_id: uuid.UUID = Header(..., alias="x-client-id"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    """Lista os agentes em uma pasta específica"""
    # Verifica se o usuário tem acesso aos dados deste cliente
    await verify_user_client(payload, db, x_client_id)

    # Verifica se a pasta existe
    folder = agent_service.get_agent_folder(db, folder_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pasta não encontrada"
        )

    # Verifica se a pasta pertence ao cliente informado
    if folder.client_id != x_client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pasta não pertence ao cliente informado",
        )

    # Lista os agentes da pasta
    agents = agent_service.get_agents_by_folder(db, folder_id, skip, limit)

    # Adiciona URL do agent card quando necessário
    for agent in agents:
        if not agent.agent_card_url:
            agent.agent_card_url = agent.agent_card_url_property

    return agents


@router.put("/{agent_id}/folder", response_model=Agent)
async def assign_agent_to_folder(
    agent_id: uuid.UUID,
    folder_id: Optional[uuid.UUID] = None,
    x_client_id: uuid.UUID = Header(..., alias="x-client-id"),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    """Atribui um agente a uma pasta ou remove da pasta atual (se folder_id=None)"""
    # Verifica se o usuário tem acesso aos dados deste cliente
    await verify_user_client(payload, db, x_client_id)

    # Verifica se o agente existe
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado"
        )

    # Verifica se o agente pertence ao cliente informado
    if agent.client_id != x_client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agente não pertence ao cliente informado",
        )

    # Se folder_id for fornecido, verifica se a pasta existe e pertence ao mesmo cliente
    if folder_id:
        folder = agent_service.get_agent_folder(db, folder_id)
        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Pasta não encontrada"
            )

        if folder.client_id != x_client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Pasta não pertence ao cliente informado",
            )

    # Atribui o agente à pasta ou remove da pasta atual
    updated_agent = agent_service.assign_agent_to_folder(db, agent_id, folder_id)

    if not updated_agent.agent_card_url:
        updated_agent.agent_card_url = updated_agent.agent_card_url_property

    return updated_agent


# Modificação nas rotas existentes para suportar filtro por pasta
@router.get("/", response_model=List[Agent])
async def read_agents(
    x_client_id: uuid.UUID = Header(..., alias="x-client-id"),
    skip: int = 0,
    limit: int = 100,
    folder_id: Optional[uuid.UUID] = Query(None, description="Filtrar por pasta"),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verify if the user has access to this client's data
    await verify_user_client(payload, db, x_client_id)

    # Get agents with optional folder filter
    agents = agent_service.get_agents_by_client(
        db, x_client_id, skip, limit, True, folder_id
    )

    for agent in agents:
        if not agent.agent_card_url:
            agent.agent_card_url = agent.agent_card_url_property

    return agents


@router.post("/", response_model=Agent, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent: AgentCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verify if the user has access to the agent's client
    await verify_user_client(payload, db, agent.client_id)

    db_agent = await agent_service.create_agent(db, agent)

    if not db_agent.agent_card_url:
        db_agent.agent_card_url = db_agent.agent_card_url_property

    return db_agent


@router.get("/{agent_id}", response_model=Agent)
async def read_agent(
    agent_id: uuid.UUID,
    x_client_id: uuid.UUID = Header(..., alias="x-client-id"),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    db_agent = agent_service.get_agent(db, agent_id)
    if db_agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )

    # Verify if the user has access to the agent's client
    await verify_user_client(payload, db, x_client_id)

    if not db_agent.agent_card_url:
        db_agent.agent_card_url = db_agent.agent_card_url_property

    return db_agent


@router.put("/{agent_id}", response_model=Agent)
async def update_agent(
    agent_id: uuid.UUID,
    agent_data: Dict[str, Any],
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Get the current agent
    db_agent = agent_service.get_agent(db, agent_id)
    if db_agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )

    # Verify if the user has access to the agent's client
    await verify_user_client(payload, db, db_agent.client_id)

    # If trying to change the client_id, verify permission for the new client as well
    if "client_id" in agent_data and agent_data["client_id"] != str(db_agent.client_id):
        new_client_id = uuid.UUID(agent_data["client_id"])
        await verify_user_client(payload, db, new_client_id)

    updated_agent = await agent_service.update_agent(db, agent_id, agent_data)

    if not updated_agent.agent_card_url:
        updated_agent.agent_card_url = updated_agent.agent_card_url_property

    return updated_agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Get the agent
    db_agent = agent_service.get_agent(db, agent_id)
    if db_agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )

    # Verify if the user has access to the agent's client
    await verify_user_client(payload, db, db_agent.client_id)

    if not agent_service.delete_agent(db, agent_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )
