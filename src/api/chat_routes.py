from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.core.jwt_middleware import (
    get_jwt_token,
    verify_user_client,
    get_jwt_token_ws,
)
from src.services import (
    agent_service,
)
from src.schemas.chat import ChatRequest, ChatResponse, ErrorResponse
from src.services.agent_runner import run_agent, run_agent_stream
from src.core.exceptions import AgentNotFoundError
from src.services.service_providers import (
    session_service,
    artifacts_service,
    memory_service,
)

from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={404: {"description": "Not found"}},
)


@router.websocket("/ws/{agent_id}/{contact_id}")
async def websocket_chat(
    websocket: WebSocket,
    agent_id: str,
    contact_id: str,
    db: Session = Depends(get_db),
):
    try:
        # Accept the connection
        await websocket.accept()
        logger.info("WebSocket connection accepted, waiting for authentication")

        # Aguardar mensagem de autenticação
        try:
            auth_data = await websocket.receive_json()
            logger.info(f"Received authentication data: {auth_data}")

            if not auth_data.get("type") == "authorization" or not auth_data.get(
                "token"
            ):
                logger.warning("Invalid authentication message")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            token = auth_data["token"]
            # Verify the token
            payload = await get_jwt_token_ws(token)
            if not payload:
                logger.warning("Invalid token")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            # Verificar se o agente pertence ao cliente do usuário
            agent = agent_service.get_agent(db, agent_id)
            if not agent:
                logger.warning(f"Agent {agent_id} not found")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            # Verificar se o usuário tem acesso ao agente (via client)
            await verify_user_client(payload, db, agent.client_id)

            logger.info(
                f"WebSocket connection established for agent {agent_id} and contact {contact_id}"
            )

            while True:
                try:
                    data = await websocket.receive_json()
                    logger.info(f"Received message: {data}")
                    message = data.get("message")

                    if not message:
                        continue

                    async for chunk in run_agent_stream(
                        agent_id=agent_id,
                        contact_id=contact_id,
                        message=message,
                        session_service=session_service,
                        artifacts_service=artifacts_service,
                        memory_service=memory_service,
                        db=db,
                    ):
                        # Enviar cada chunk como uma mensagem JSON
                        await websocket.send_json(
                            {"message": chunk, "turn_complete": False}
                        )

                    # Enviar sinal de turno completo
                    await websocket.send_json({"message": "", "turn_complete": True})

                except WebSocketDisconnect:
                    logger.info("Client disconnected")
                    break
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON message received")
                    continue
                except Exception as e:
                    logger.error(f"Error in WebSocket message handling: {str(e)}")
                    await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                    break

        except WebSocketDisconnect:
            logger.info("Client disconnected during authentication")
        except json.JSONDecodeError:
            logger.warning("Invalid authentication message format")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        except Exception as e:
            logger.error(f"Error during authentication: {str(e)}")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)


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
