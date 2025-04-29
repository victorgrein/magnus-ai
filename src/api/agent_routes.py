from datetime import datetime
import os
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
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
from src.services.agent_runner import run_agent
from src.services.service_providers import (
    session_service,
    artifacts_service,
    memory_service,
)
import logging

from src.services.session_service import get_session_events

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

    return agent_service.create_agent(db, agent)


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

    return agent_service.get_agents_by_client(db, x_client_id, skip, limit)


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


@router.get("/{agent_id}/.well-known/agent.json")
async def get_agent_json(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        agent = agent_service.get_agent(db, agent_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
            )

        mcp_servers = agent.config.get("mcp_servers", [])
        formatted_tools = await format_agent_tools(mcp_servers, db)

        AGENT_CARD = {
            "name": agent.name,
            "description": agent.description,
            "url": f"{os.getenv('API_URL', '')}/api/v1/agents/{agent.id}",
            "provider": {
                "organization": os.getenv("ORGANIZATION_NAME", ""),
                "url": os.getenv("ORGANIZATION_URL", ""),
            },
            "version": os.getenv("API_VERSION", ""),
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": True,
            },
            "authentication": {
                "schemes": ["apiKey"],
                "credentials": {"in": "header", "name": "x-api-key"},
            },
            "defaultInputModes": ["text", "application/json"],
            "defaultOutputModes": ["text", "application/json"],
            "skills": formatted_tools,
        }
        return AGENT_CARD
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating agent card",
        )


@router.post("/{agent_id}/tasks/send")
async def handle_task(
    agent_id: uuid.UUID,
    request: Request,
    x_api_key: str = Header(..., alias="x-api-key"),
    db: Session = Depends(get_db),
):
    """Endpoint to clients A2A send a new task (with an initial user message)."""
    try:
        # Verify agent
        agent = agent_service.get_agent(db, agent_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
            )

        # Verify API key
        agent_config = agent.config
        if agent_config.get("api_key") != x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key for this agent",
            )

        # Process request
        try:
            task_request = await request.json()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request format"
            )

        # Validate required fields
        task_id = task_request.get("id")
        if not task_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Task ID is required"
            )

        # Extract user message
        try:
            user_message = task_request["message"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message format"
            )

        # Configure session and metadata
        session_id = f"{task_id}_{agent_id}"
        metadata = task_request.get("metadata", {})
        history_length = metadata.get("historyLength", 50)

        # Initialize response
        response_task = {
            "id": task_id,
            "sessionId": session_id,
            "status": {
                "state": "running",
                "timestamp": datetime.now().isoformat(),
                "message": None,
                "error": None,
            },
            "artifacts": [],
            "history": [],
            "metadata": metadata,
        }

        try:
            # Execute agent
            final_response_text = await run_agent(
                str(agent_id),
                task_id,
                user_message,
                session_service,
                artifacts_service,
                memory_service,
                db,
                session_id,
            )

            # Update status to completed
            response_task["status"].update(
                {
                    "state": "completed",
                    "timestamp": datetime.now().isoformat(),
                    "message": {
                        "role": "agent",
                        "parts": [{"type": "text", "text": final_response_text}],
                    },
                }
            )

            # Add artifacts
            if final_response_text:
                response_task["artifacts"].append(
                    {
                        "type": "text",
                        "content": final_response_text,
                        "metadata": {
                            "generated_at": datetime.now().isoformat(),
                            "content_type": "text/plain",
                        },
                    }
                )

        except Exception as e:
            # Update status to failed
            response_task["status"].update(
                {
                    "state": "failed",
                    "timestamp": datetime.now().isoformat(),
                    "error": {"code": "AGENT_EXECUTION_ERROR", "message": str(e)},
                }
            )

        # Process history
        try:
            history_messages = get_session_events(session_service, session_id)
            history_messages = history_messages[-history_length:]

            formatted_history = []
            for event in history_messages:
                if event.content and event.content.parts:
                    role = (
                        "agent" if event.content.role == "model" else event.content.role
                    )
                    formatted_history.append(
                        {
                            "role": role,
                            "parts": [
                                {"type": "text", "text": part.text}
                                for part in event.content.parts
                                if part.text
                            ],
                        }
                    )

            response_task["history"] = formatted_history

        except Exception as e:
            logger.error(f"Error processing history: {str(e)}")
        return response_task

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in handle_task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
