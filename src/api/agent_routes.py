from fastapi import APIRouter, Depends, HTTPException, status
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
)
import logging

logger = logging.getLogger(__name__)


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

    return agent_service.create_agent(db, agent)


@router.get("/{client_id}", response_model=List[Agent])
async def read_agents(
    client_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verify if the user has access to this client's data
    await verify_user_client(payload, db, client_id)

    return agent_service.get_agents_by_client(db, client_id, skip, limit)


@router.get("/{agent_id}", response_model=Agent)
async def read_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    db_agent = agent_service.get_agent(db, agent_id)
    if db_agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )

    # Verify if the user has access to the agent's client
    await verify_user_client(payload, db, db_agent.client_id)

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

    return await agent_service.update_agent(db, agent_id, agent_data)


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
