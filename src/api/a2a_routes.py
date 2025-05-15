"""
┌──────────────────────────────────────────────────────────────────────────────┐
│ @author: Davidson Gomes                                                      │
│ @file: a2a_routes.py                                                         │
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

"""
Routes for the A2A (Agent-to-Agent) protocol.

This module implements the standard A2A routes according to the specification.
Supports both text messages and file uploads through the message parts mechanism.
"""

import uuid
import logging
import json
from fastapi import APIRouter, Depends, Header, Request, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from src.models.models import Agent
from src.config.database import get_db
from src.services.a2a_task_manager import (
    A2ATaskManager,
    A2AService,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/a2a",
    tags=["a2a"],
    responses={
        404: {"description": "Not found"},
        400: {"description": "Bad request"},
        401: {"description": "Unauthorized"},
        500: {"description": "Internal server error"},
    },
)


def get_a2a_service(db: Session = Depends(get_db)):
    task_manager = A2ATaskManager(db)
    return A2AService(db, task_manager)


async def verify_api_key(db: Session, x_api_key: str) -> bool:
    """Verifies the API key."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key not provided")

    agent = (
        db.query(Agent)
        .filter(Agent.config.has_key("api_key"))
        .filter(Agent.config["api_key"].astext == x_api_key)
        .first()
    )

    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@router.post("/{agent_id}")
async def process_a2a_request(
    agent_id: uuid.UUID,
    request: Request,
    x_api_key: str = Header(None, alias="x-api-key"),
    db: Session = Depends(get_db),
    a2a_service: A2AService = Depends(get_a2a_service),
):
    """
    Processes an A2A request.

    Supports both text messages and file uploads. For file uploads,
    include file parts in the message following the A2A protocol format:

    {
        "jsonrpc": "2.0",
        "id": "request-id",
        "method": "tasks/send",
        "params": {
            "id": "task-id",
            "sessionId": "session-id",
            "message": {
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": "Analyze this image"
                    },
                    {
                        "type": "file",
                        "file": {
                            "name": "example.jpg",
                            "mimeType": "image/jpeg",
                            "bytes": "base64-encoded-content"
                        }
                    }
                ]
            }
        }
    }
    """
    # Verify the API key
    if not verify_api_key(db, x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Process the request
    try:
        request_body = await request.json()

        debug_request_body = {}
        if "method" in request_body:
            debug_request_body["method"] = request_body["method"]
        if "id" in request_body:
            debug_request_body["id"] = request_body["id"]

        logger.info(f"A2A request received: {debug_request_body}")

        # Log if request contains file parts for debugging
        if isinstance(request_body, dict) and "params" in request_body:
            params = request_body.get("params", {})
            message = params.get("message", {})
            parts = message.get("parts", [])

            logger.info(f"A2A message contains {len(parts)} parts")
            for i, part in enumerate(parts):
                if not isinstance(part, dict):
                    logger.warning(f"Part {i+1} is not a dictionary: {type(part)}")
                    continue

                part_type = part.get("type")
                logger.info(f"Part {i+1} type: {part_type}")

                if part_type == "file":
                    file_info = part.get("file", {})
                    logger.info(
                        f"File part found: {file_info.get('name')} ({file_info.get('mimeType')})"
                    )
                    if "bytes" in file_info:
                        bytes_data = file_info.get("bytes", "")
                        bytes_size = len(bytes_data) * 0.75
                        logger.info(f"File size: ~{bytes_size/1024:.2f} KB")
                        if bytes_data:
                            sample = (
                                bytes_data[:10] + "..."
                                if len(bytes_data) > 10
                                else bytes_data
                            )
                            logger.info(f"Sample of base64 data: {sample}")
                elif part_type == "text":
                    text_content = part.get("text", "")
                    preview = (
                        text_content[:30] + "..."
                        if len(text_content) > 30
                        else text_content
                    )
                    logger.info(f"Text part found: '{preview}'")

        result = await a2a_service.process_request(agent_id, request_body)

        # If the response is a streaming response, return as EventSourceResponse
        if hasattr(result, "__aiter__"):
            logger.info("Returning streaming response")

            async def event_generator():
                async for item in result:
                    if hasattr(item, "model_dump_json"):
                        yield {"data": item.model_dump_json(exclude_none=True)}
                    else:
                        yield {"data": json.dumps(item)}

            return EventSourceResponse(event_generator())

        # Otherwise, return as JSONResponse
        logger.info("Returning standard JSON response")
        if hasattr(result, "model_dump"):
            return JSONResponse(result.model_dump(exclude_none=True))
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Error processing A2A request: {e}")
        import traceback

        logger.error(f"Full traceback: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": "Internal server error"},
            },
        )


@router.get("/{agent_id}/.well-known/agent.json")
async def get_agent_card(
    agent_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    a2a_service: A2AService = Depends(get_a2a_service),
):
    """Gets the agent card for the specified agent."""
    try:
        agent_card = a2a_service.get_agent_card(agent_id)
        if hasattr(agent_card, "model_dump"):
            return JSONResponse(agent_card.model_dump(exclude_none=True))
        return JSONResponse(agent_card)
    except Exception as e:
        logger.error(f"Error getting agent card: {e}")
        return JSONResponse(
            status_code=404,
            content={"error": f"Agent not found: {str(e)}"},
        )
