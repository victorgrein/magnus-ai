"""
┌──────────────────────────────────────────────────────────────────────────────┐
│ @author: Davidson Gomes                                                      │
│ @file: run_seeders.py                                                        │
│ Developed by: Davidson Gomes                                                 │
│ Creation date: May 13, 2025                                                  │
│ Contact: contato@evolution-api.com                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│ @copyright © Evolution API 2025. All rights reserved.                        │
│ Licensed under the Apache License, Version 2.0                               │
│                                                                              │
│ You may not use this file except in compliance with the License.             │
│ You may obtain a copy of the License at                                      │
│                                                                              │
│    http://www.apache.org/licenses/LICENSE-2.0                                │
│                                                                              │
│ Unless required by applicable law or agreed to in writing, software          │
│ distributed under the License is distributed on an "AS IS" BASIS,            │
│ WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.     │
│ See the License for the specific language governing permissions and          │
│ limitations under the License.                                               │
├──────────────────────────────────────────────────────────────────────────────┤
│ @important                                                                   │
│ For any future changes to the code in this file, it is recommended to        │
│ include, together with the modification, the information of the developer    │
│ who changed it and the date of modification.                                 │
└──────────────────────────────────────────────────────────────────────────────┘
"""

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


@router.websocket("/ws/{agent_id}/{external_id}")
async def websocket_chat(
    websocket: WebSocket,
    agent_id: str,
    external_id: str,
    db: Session = Depends(get_db),
):
    try:
        # Accept the connection
        await websocket.accept()
        logger.info("WebSocket connection accepted, waiting for authentication")

        # Wait for authentication message
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

            # Verify if the agent belongs to the user's client
            agent = agent_service.get_agent(db, agent_id)
            if not agent:
                logger.warning(f"Agent {agent_id} not found")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            # Verify if the user has access to the agent (via client)
            await verify_user_client(payload, db, agent.client_id)

            logger.info(
                f"WebSocket connection established for agent {agent_id} and external_id {external_id}"
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
                        external_id=external_id,
                        message=message,
                        session_service=session_service,
                        artifacts_service=artifacts_service,
                        memory_service=memory_service,
                        db=db,
                    ):
                        await websocket.send_json(
                            {"message": json.loads(chunk), "turn_complete": False}
                        )

                    # Send signal of complete turn
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
    "",
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
            request.external_id,
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
