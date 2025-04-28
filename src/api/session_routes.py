from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.config.database import get_db
from typing import List
import uuid
from src.core.jwt_middleware import (
    get_jwt_token,
    verify_user_client,
)
from src.services import (
    agent_service,
)
from google.adk.events import Event
from google.adk.sessions import Session as Adk_Session
from src.services.session_service import (
    get_session_events,
    get_session_by_id,
    delete_session,
    get_sessions_by_agent,
    get_sessions_by_client,
)
from src.services.service_providers import session_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
    responses={404: {"description": "Not found"}},
)


# Session Routes
@router.get("/client/{client_id}", response_model=List[Adk_Session])
async def get_client_sessions(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verify if the user has access to this client's data
    await verify_user_client(payload, db, client_id)
    return get_sessions_by_client(db, client_id)


@router.get("/agent/{agent_id}", response_model=List[Adk_Session])
async def get_agent_sessions(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
    skip: int = 0,
    limit: int = 100,
):
    # Verify if the agent belongs to the user's client
    agent = agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )

    # Verify if the user has access to the agent (via client)
    await verify_user_client(payload, db, agent.client_id)

    return get_sessions_by_agent(db, agent_id, skip, limit)


@router.get("/{session_id}", response_model=Adk_Session)
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Get the session
    session = get_session_by_id(session_service, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # Verify if the session's agent belongs to the user's client
    agent_id = uuid.UUID(session.agent_id) if session.agent_id else None
    if agent_id:
        agent = agent_service.get_agent(db, agent_id)
        if agent:
            await verify_user_client(payload, db, agent.client_id)

    return session


@router.get(
    "/{session_id}/messages",
    response_model=List[Event],
)
async def get_agent_messages(
    session_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Get the session
    session = get_session_by_id(session_service, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # Verify if the session's agent belongs to the user's client
    agent_id = uuid.UUID(session.agent_id) if session.agent_id else None
    if agent_id:
        agent = agent_service.get_agent(db, agent_id)
        if agent:
            await verify_user_client(payload, db, agent.client_id)

    return get_session_events(session_service, session_id)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_session(
    session_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Get the session
    session = get_session_by_id(session_service, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # Verify if the session's agent belongs to the user's client
    agent_id = uuid.UUID(session.agent_id) if session.agent_id else None
    if agent_id:
        agent = agent_service.get_agent(db, agent_id)
        if agent:
            await verify_user_client(payload, db, agent.client_id)

    return delete_session(session_service, session_id)
