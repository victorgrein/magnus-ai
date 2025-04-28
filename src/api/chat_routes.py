from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.core.jwt_middleware import (
    get_jwt_token,
    verify_user_client,
)
from src.services import (
    agent_service,
)
from src.schemas.chat import ChatRequest, ChatResponse, ErrorResponse
from src.services.agent_runner import run_agent
from src.core.exceptions import AgentNotFoundError
from src.services.service_providers import (
    session_service,
    artifacts_service,
    memory_service,
)

from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/",
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
    # Verify if the agent belongs to the user's client
    agent = agent_service.get_agent(db, request.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )

    # Verify if the user has access to the agent (via client)
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
