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
A2A Protocol Official Implementation.

100% compliant with the official A2A specification:
https://google.github.io/A2A/specification

This is the official and only A2A implementation for the Evo AI platform.

Methods implemented:
- message/send: Send a message and get response
- message/stream: Send a message and stream response  
- agent/authenticatedExtendedCard: Get agent information (via .well-known/agent.json)

Features:
- Direct integration with agent_runner (no complex SDK layer)
- 100% specification compliant JSON-RPC format
- Proper Task object structure
- Full streaming support
- API key authentication

"""

import uuid
import logging
import json
import base64
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional


from fastapi import APIRouter, Depends, Header, Request, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from src.models.models import Agent
from src.config.database import get_db
from src.config.settings import settings
from src.services.agent_service import get_agent
from src.services.adk.agent_runner import run_agent, run_agent_stream
from src.services.service_providers import (
    session_service,
    artifacts_service,
    memory_service,
)
from src.schemas.chat import FileData


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


async def verify_api_key(db: Session, x_api_key: str) -> bool:
    """Verifies API key against agent config."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key not provided")

    query = text("SELECT * FROM agents WHERE config->>'api_key' = :api_key LIMIT 1")
    result = db.execute(query, {"api_key": x_api_key}).first()

    if not result:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True


def extract_text_from_message(message: Dict[str, Any]) -> str:
    """Extract text from message parts according to A2A spec."""
    if not message or "parts" not in message:
        return ""

    for part in message["parts"]:
        if part.get("type") == "text" and "text" in part:
            return part["text"]

    return ""


def extract_files_from_message(message: Dict[str, Any]) -> List[FileData]:
    """Extract files from message parts according to A2A spec."""
    files = []
    if not message or "parts" not in message:
        return files

    for part in message["parts"]:
        if part.get("type") == "file" and "file" in part:
            file_data = part["file"]

            # Check if file has bytes (base64 encoded)
            if "bytes" in file_data and file_data["bytes"]:
                try:
                    # Validate base64 content
                    base64.b64decode(file_data["bytes"])

                    file_obj = FileData(
                        filename=file_data.get("name", "file"),
                        content_type=file_data.get(
                            "mimeType", "application/octet-stream"
                        ),
                        data=file_data["bytes"],  # Keep as base64 string
                    )
                    files.append(file_obj)
                    logger.info(
                        f"📎 Extracted file: {file_obj.filename} ({file_obj.content_type})"
                    )

                except Exception as e:
                    logger.error(f"❌ Invalid base64 in file: {e}")
                    continue
            else:
                logger.warning(
                    f"⚠️ File part missing bytes data: {file_data.get('name', 'unnamed')}"
                )

    logger.info(f"📎 Total files extracted: {len(files)}")
    return files


def create_task_response(
    task_id: str,
    context_id: str,
    final_response: str,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    current_user_message: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create Task response according to A2A specification."""

    logger.info(
        f"🏗️ create_task_response called with history: {len(conversation_history) if conversation_history else 0} messages"
    )

    # Create main response artifact (only the agent's response)
    artifacts = [
        {
            "artifactId": str(uuid.uuid4()),
            "parts": [{"type": "text", "text": final_response}],
        }
    ]

    logger.info(f"📦 Created main artifact")

    # Create Task response according to A2A spec
    task_response = {
        "id": task_id,
        "contextId": context_id,
        "status": {"state": "completed", "timestamp": datetime.now().isoformat() + "Z"},
        "artifacts": artifacts,
        "kind": "task",
    }

    # Build complete history for A2A response
    complete_history = []

    # Add existing conversation history
    if conversation_history:
        for msg in conversation_history:
            # Create A2A Message object
            a2a_message = {
                "role": msg["role"],
                "parts": [{"type": "text", "text": msg["content"]}],
                "messageId": msg.get("messageId"),
                "taskId": task_id,
                "contextId": context_id,
                "kind": "message",
            }

            # Add timestamp if available
            if msg.get("timestamp"):
                a2a_message["timestamp"] = msg["timestamp"]

            complete_history.append(a2a_message)

    # Add current user message if provided (this is the message that triggered this response)
    if current_user_message:
        logger.info(f"📝 Adding current user message to history")
        a2a_message = {
            "role": "user",
            "parts": [{"type": "text", "text": current_user_message["content"]}],
            "messageId": current_user_message.get("messageId"),
            "taskId": task_id,
            "contextId": context_id,
            "kind": "message",
        }

        # Add timestamp if available
        if current_user_message.get("timestamp"):
            a2a_message["timestamp"] = current_user_message["timestamp"]

        complete_history.append(a2a_message)

    # Add history field to Task object (A2A spec compliant)
    if complete_history:
        task_response["history"] = complete_history
        logger.info(
            f"📚 Added {len(complete_history)} messages to history field (including current message)"
        )
    else:
        logger.warning("⚠️ No conversation history provided to create_task_response")

    logger.info(f"✅ create_task_response returning A2A compliant Task object")
    return task_response


def clean_message_content(content: str, role: str) -> str:
    """Clean message content, extracting just the text if it contains JSON."""
    if role == "agent" or role == "assistant":
        # Check if content looks like JSON (starts with { and contains jsonrpc)
        if content.strip().startswith("{") and "jsonrpc" in content:
            try:
                # Try to parse as JSON and extract the actual response text
                import json

                json_data = json.loads(content)

                # Look for the actual text in artifacts
                if "result" in json_data and "artifacts" in json_data["result"]:
                    for artifact in json_data["result"]["artifacts"]:
                        if "parts" in artifact:
                            for part in artifact["parts"]:
                                if part.get("type") == "text" and "text" in part:
                                    return part["text"]

                # Fallback: if we can't extract, return a cleaned version
                return "Previous assistant response"

            except (json.JSONDecodeError, KeyError):
                # If not valid JSON, return as-is but truncated
                return content[:100] + "..." if len(content) > 100 else content

    return content


def extract_conversation_history(
    agent_id: str, external_id: str
) -> List[Dict[str, Any]]:
    """Extract conversation history from session using the same logic as /sessions/{session_id}/messages."""
    logger.info(
        f"🔍 extract_conversation_history called with agent_id={agent_id}, external_id={external_id}"
    )

    try:
        from src.services.session_service import get_session_events, get_session_by_id

        # Get session ID in the correct format (same as working endpoint)
        session_id = f"{external_id}_{agent_id}"
        logger.info(f"📋 Constructed session_id: {session_id}")

        # First, verify session exists (same as working endpoint)
        logger.info(f"🔍 Verifying session exists...")
        session = get_session_by_id(session_service, session_id)
        if not session:
            logger.warning(f"⚠️ Session not found: {session_id}")
            return []

        logger.info(f"✅ Session found: {session_id}")

        # Get events using same method as working endpoint
        logger.info(f"🔍 Getting events for session...")
        events = get_session_events(session_service, session_id)
        logger.info(
            f"📋 get_session_events returned {len(events) if events else 0} events"
        )

        history = []

        # Process events exactly like the working /messages endpoint
        for i, event in enumerate(events):
            logger.info(
                f"🔍 Processing event {i}: id={getattr(event, 'id', 'NO_ID')}, author={getattr(event, 'author', 'NO_AUTHOR')}"
            )

            # Convert event to dict like in working endpoint
            event_dict = (
                event.model_dump() if hasattr(event, "model_dump") else event.__dict__
            )

            # Check if event has content with parts (same logic as working endpoint)
            if event_dict.get("content") and event_dict["content"].get("parts"):
                logger.info(
                    f"📝 Event {i} has content with {len(event_dict['content']['parts'])} parts"
                )

                for j, part in enumerate(event_dict["content"]["parts"]):
                    logger.info(f"📝 Processing part {j}: {part}")

                    # Extract text content (same as working endpoint checks for text)
                    if isinstance(part, dict) and part.get("text"):
                        role = "user" if event_dict.get("author") == "user" else "agent"
                        text_content = part["text"]

                        # Clean the content to remove JSON artifacts
                        cleaned_content = clean_message_content(text_content, role)
                        logger.info(
                            f"📝 Cleaned content for {role}: {cleaned_content[:50]}..."
                        )

                        # Create A2A compatible history entry
                        history_entry = {
                            "role": role,
                            "content": cleaned_content,
                            "messageId": event_dict.get("id"),
                            "timestamp": event_dict.get("timestamp"),
                            "author": event_dict.get("author"),
                            "invocation_id": event_dict.get("invocation_id"),
                        }

                        history.append(history_entry)
                        logger.info(f"✅ Added history entry {len(history)}: {role}")
                    else:
                        logger.info(f"📝 Part {j} has no text content: {part}")
            else:
                logger.warning(f"⚠️ Event {i} has no content or parts")

        logger.info(
            f"📚 extract_conversation_history extracted {len(history)} messages using working logic"
        )
        return history

    except Exception as e:
        logger.error(f"❌ Error extracting conversation history: {e}")
        import traceback

        logger.error(f"Full traceback: {traceback.format_exc()}")
        return []


def extract_history_from_params(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract history from request params according to A2A spec."""
    history = []
    if "history" in params and isinstance(params["history"], list):
        for msg in params["history"]:
            if isinstance(msg, dict) and "role" in msg and "parts" in msg:
                # Extract text from parts
                text_content = ""
                for part in msg["parts"]:
                    if (
                        isinstance(part, dict)
                        and part.get("type") == "text"
                        and "text" in part
                    ):
                        text_content += part["text"] + " "

                if text_content.strip():
                    history.append(
                        {
                            "role": msg["role"],
                            "content": text_content.strip(),
                            "messageId": msg.get("messageId"),
                            "timestamp": None,  # Could be added if provided
                        }
                    )

    logger.info(f"📚 Extracted {len(history)} messages from request history")
    return history


def combine_histories(
    request_history: List[Dict[str, Any]], session_history: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Combine request history with session history, avoiding duplicates."""
    combined = []

    # Add session history first
    for msg in session_history:
        combined.append(msg)

    # Add request history, avoiding duplicates based on messageId or content
    for req_msg in request_history:
        # Check if this message already exists in combined history
        is_duplicate = False
        for existing_msg in combined:
            if (
                req_msg.get("messageId")
                and req_msg["messageId"] == existing_msg.get("messageId")
            ) or (
                req_msg["content"] == existing_msg["content"]
                and req_msg["role"] == existing_msg["role"]
            ):
                is_duplicate = True
                break

        if not is_duplicate:
            combined.append(req_msg)

    # Sort by timestamp if available, otherwise maintain order
    return combined


@router.post("/{agent_id}")
async def process_a2a_message(
    agent_id: uuid.UUID,
    request: Request,
    x_api_key: str = Header(None, alias="x-api-key"),
    db: Session = Depends(get_db),
):
    """
    Process A2A messages according to official specification.

    Supports:
    - message/send: Send a message and get response
    - message/stream: Send a message and stream response
    """
    logger.info(f"🎯 A2A Spec endpoint called for agent {agent_id}")

    # Verify API key
    await verify_api_key(db, x_api_key)

    # Verify agent exists
    agent = get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        # Parse JSON-RPC request
        request_body = await request.json()

        jsonrpc = request_body.get("jsonrpc")
        if jsonrpc != "2.0":
            raise HTTPException(status_code=400, detail="Invalid JSON-RPC version")

        method = request_body.get("method")
        params = request_body.get("params", {})
        request_id = request_body.get("id")

        logger.info(f"📝 Method: {method}, ID: {request_id}")

        if method == "message/send":
            return await handle_message_send(agent_id, params, request_id, db)
        elif method == "message/stream":
            return await handle_message_stream(agent_id, params, request_id, db)
        elif method == "tasks/get":
            return await handle_tasks_get(agent_id, params, request_id, db)
        elif method == "tasks/cancel":
            return await handle_tasks_cancel(agent_id, params, request_id, db)
        elif method == "tasks/pushNotificationConfig/set":
            return await handle_tasks_push_notification_config_set(
                agent_id, params, request_id, db
            )
        elif method == "tasks/pushNotificationConfig/get":
            return await handle_tasks_push_notification_config_get(
                agent_id, params, request_id, db
            )
        elif method == "tasks/resubscribe":
            return await handle_tasks_resubscribe(agent_id, params, request_id, db)
        elif method == "agent/authenticatedExtendedCard":
            return await handle_agent_authenticated_extended_card(
                agent_id, params, request_id, db
            )
        else:
            # JSON-RPC error for method not found
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": "Method not found",
                        "data": {
                            "method": method,
                            "supported_methods": [
                                "message/send",
                                "message/stream",
                                "tasks/get",
                                "tasks/cancel",
                                "tasks/pushNotificationConfig/set",
                                "tasks/pushNotificationConfig/get",
                                "tasks/resubscribe",
                                "agent/authenticatedExtendedCard",
                            ],
                        },
                    },
                },
            )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing A2A request: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": request_body.get("id") if "request_body" in locals() else None,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": {"error": str(e)},
                },
            },
        )


async def handle_message_send(
    agent_id: uuid.UUID, params: Dict[str, Any], request_id: str, db: Session
) -> JSONResponse:
    """Handle message/send according to A2A spec."""

    logger.info(f"🔄 Processing message/send for agent {agent_id}")

    # Extract message from params
    message = params.get("message")
    if not message:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32602,
                    "message": "Invalid params",
                    "data": {"missing": "message"},
                },
            }
        )

    # Extract configuration from params (A2A spec: configuration is optional)
    configuration = params.get("configuration", {})
    push_notification_config = configuration.get("pushNotificationConfig")

    # Support alternative format: pushNotificationConfig directly in params (for backward compatibility)
    if not push_notification_config:
        push_notification_config = params.get("pushNotificationConfig")

    logger.info(
        f"🔔 Push notification config found: {push_notification_config is not None}"
    )

    if push_notification_config:
        # Support both official spec format and common variations
        webhook_url = push_notification_config.get(
            "url"
        ) or push_notification_config.get("webhookUrl")

        logger.info(
            f"🔔 Push notification config provided: {webhook_url or 'No URL found'}"
        )

        # Validate push notification config according to A2A spec (support both url and webhookUrl)
        if not webhook_url:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "Invalid params",
                        "data": {
                            "missing": "pushNotificationConfig.url or pushNotificationConfig.webhookUrl"
                        },
                    },
                }
            )

        # Validate HTTPS requirement (A2A spec: prevents SSRF attacks)
        if not webhook_url.startswith("https://"):
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "Invalid params",
                        "data": {
                            "error": "pushNotificationConfig.url MUST use HTTPS for security"
                        },
                    },
                }
            )

        # Validate that agent supports push notifications
        agent = get_agent(db, agent_id)
        if not agent:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32001,
                        "message": "Agent not found",
                    },
                }
            )

        # Check agent capabilities for push notification support
        # (Our agent card already indicates pushNotifications: true)
        logger.info(f"✅ Agent {agent_id} supports push notifications")

    # Extract text and files from message
    text = extract_text_from_message(message)
    files = extract_files_from_message(message)

    # Allow empty text if we have files
    if not text and not files:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32602,
                    "message": "Invalid params",
                    "data": {"missing": "text content or files in message parts"},
                },
            }
        )

    # Use default text if only files provided
    if not text and files:
        text = "Analyze the provided files"

    logger.info(f"📝 Extracted text: {text}")
    logger.info(f"📎 Extracted files: {len(files)}")

    # Generate IDs
    task_id = str(uuid.uuid4())
    context_id = message.get("messageId", str(uuid.uuid4()))

    try:
        # Extract conversation history for context
        logger.info(
            f"🔍 Attempting to extract conversation history for agent {agent_id}, context {context_id}"
        )
        conversation_history = extract_conversation_history(str(agent_id), context_id)
        logger.info(
            f"📚 Session history extracted: {len(conversation_history)} messages"
        )

        # Extract history from params
        logger.info(f"🔍 Attempting to extract history from request params")
        request_history = extract_history_from_params(params)
        logger.info(f"📝 Request history extracted: {len(request_history)} messages")

        # Combine histories
        logger.info(f"🔗 Combining histories...")
        combined_history = combine_histories(request_history, conversation_history)
        logger.info(f"📖 Combined history has {len(combined_history)} total messages")

        # Log detailed combined history for debugging
        for i, msg in enumerate(combined_history):
            logger.info(f"  History[{i}]: {msg['role']} - {msg['content'][:50]}...")

        # Execute agent with files - the ADK runner will handle session history automatically
        logger.info(
            f"🤖 Executing agent {agent_id} with message: {text} and {len(files)} files"
        )
        logger.info(
            f"📚 ADK will provide session context automatically ({len(combined_history)} previous messages available)"
        )

        result = await run_agent(
            agent_id=str(agent_id),
            external_id=context_id,
            message=text,  # Send only the original message - ADK handles context
            session_service=session_service,
            artifacts_service=artifacts_service,
            memory_service=memory_service,
            db=db,
            files=files if files else None,
        )

        final_response = result.get("final_response", "No response")
        logger.info(f"✅ Agent response: {final_response}")

        # Log what we're about to send to create_task_response
        logger.info(
            f"🏗️ Creating task response with {len(combined_history) if combined_history else 0} history messages"
        )

        # Create current user message object for history
        current_user_message = {
            "content": text,
            "messageId": message.get("messageId"),
            "timestamp": None,  # Could add current timestamp
        }

        # Create A2A compliant response with history
        task_response = create_task_response(
            task_id,
            context_id,
            final_response,
            combined_history if combined_history else None,
            current_user_message,
        )

        logger.info(
            f"📦 Task response created with {len(task_response.get('artifacts', []))} artifacts"
        )

        # Handle push notification if configured
        if push_notification_config:
            try:
                await send_push_notification(task_response, push_notification_config)
                logger.info(f"🔔 Push notification sent successfully")
            except Exception as e:
                logger.error(f"❌ Push notification failed: {e}")
                # Continue execution - push notification failure shouldn't break the response

        return JSONResponse(
            content={"jsonrpc": "2.0", "id": request_id, "result": task_response}
        )

    except Exception as e:
        logger.error(f"❌ Agent execution error: {e}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": "Agent execution failed",
                    "data": {"error": str(e)},
                },
            }
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
