from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from src.config.database import get_db
from typing import List, Dict, Any
import uuid
from src.core.jwt_middleware import (
    get_jwt_token,
    verify_user_client,
)
from src.schemas.schemas import (
    Agent,
    AgentCreate,
)
from src.services import (
    agent_service,
    mcp_server_service,
)
from src.models.models import Agent as AgentModel
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


@router.get("/", response_model=List[Agent])
async def read_agents(
    x_client_id: uuid.UUID = Header(..., alias="x-client-id"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verify if the user has access to this client's data
    await verify_user_client(payload, db, x_client_id)

    agents = agent_service.get_agents_by_client(db, x_client_id, skip, limit)

    for agent in agents:
        if not agent.agent_card_url:
            agent.agent_card_url = agent.agent_card_url_property

    return agents


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
