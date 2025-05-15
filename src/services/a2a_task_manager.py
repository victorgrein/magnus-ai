"""
┌──────────────────────────────────────────────────────────────────────────────┐
│ @author: Davidson Gomes                                                      │
│ @file: a2a_task_manager.py                                                   │
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

import logging
import asyncio
from collections.abc import AsyncIterable
from typing import Dict, Optional
from uuid import UUID
import json
import base64
import uuid as uuid_pkg

from sqlalchemy.orm import Session
from google.genai.types import Part, Blob

from src.config.settings import settings
from src.services.agent_service import (
    get_agent,
)
from src.services.mcp_server_service import get_mcp_server

from src.services.agent_runner import run_agent, run_agent_stream
from src.services.service_providers import (
    session_service,
    artifacts_service,
    memory_service,
)
from src.models.models import Agent
from src.schemas.a2a_types import (
    A2ARequest,
    GetTaskRequest,
    SendTaskRequest,
    SendTaskResponse,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
    CancelTaskRequest,
    SetTaskPushNotificationRequest,
    GetTaskPushNotificationRequest,
    TaskResubscriptionRequest,
    JSONRPCResponse,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    Task,
    TaskSendParams,
    InternalError,
    Message,
    Artifact,
    TaskStatus,
    TaskState,
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    AgentAuthentication,
    AgentProvider,
)
from src.schemas.chat import FileData

logger = logging.getLogger(__name__)


class A2ATaskManager:
    """Task manager for the A2A protocol."""

    def __init__(self, db: Session):
        self.db = db
        self.tasks: Dict[str, Task] = {}
        self.lock = asyncio.Lock()

    async def upsert_task(self, task_params: TaskSendParams) -> Task:
        """Creates or updates a task in the store."""
        async with self.lock:
            task = self.tasks.get(task_params.id)
            if task is None:
                # Create new task with initial history
                task = Task(
                    id=task_params.id,
                    sessionId=task_params.sessionId,
                    status=TaskStatus(state=TaskState.SUBMITTED),
                    history=[task_params.message],
                    artifacts=[],
                )
                self.tasks[task_params.id] = task
            else:
                # Add message to existing history
                if task.history is None:
                    task.history = []
                task.history.append(task_params.message)

            return task

    async def on_get_task(self, request: GetTaskRequest) -> JSONRPCResponse:
        """Handles requests to get task details."""
        try:
            task_id = request.params.id
            history_length = request.params.historyLength

            async with self.lock:
                if task_id not in self.tasks:
                    return JSONRPCResponse(
                        id=request.id,
                        error=InternalError(message=f"Task {task_id} not found"),
                    )

                # Get the task and limit the history as requested
                task = self.tasks[task_id]
                task_result = self.append_task_history(task, history_length)

            return SendTaskResponse(id=request.id, result=task_result)
        except Exception as e:
            logger.error(f"Error getting task: {e}")
            return JSONRPCResponse(
                id=request.id,
                error=InternalError(message=f"Error getting task: {str(e)}"),
            )

    async def on_send_task(
        self, request: SendTaskRequest, agent_id: UUID
    ) -> JSONRPCResponse:
        """Handles requests to send a task for processing."""
        try:
            agent = get_agent(self.db, agent_id)
            if not agent:
                return JSONRPCResponse(
                    id=request.id,
                    error=InternalError(message=f"Agent {agent_id} not found"),
                )

            await self.upsert_task(request.params)
            return await self._process_task(request, agent)
        except Exception as e:
            logger.error(f"Error sending task: {e}")
            return JSONRPCResponse(
                id=request.id,
                error=InternalError(message=f"Error sending task: {str(e)}"),
            )

    async def on_send_task_subscribe(
        self, request: SendTaskStreamingRequest, agent_id: UUID
    ) -> AsyncIterable[SendTaskStreamingResponse]:
        """Handles requests to send a task and subscribe to updates."""
        try:
            agent = get_agent(self.db, agent_id)
            if not agent:
                yield JSONRPCResponse(
                    id=request.id,
                    error=InternalError(message=f"Agent {agent_id} not found"),
                )
                return

            await self.upsert_task(request.params)
            async for response in self._stream_task_process(request, agent):
                yield response
        except Exception as e:
            logger.error(f"Error processing streaming task: {e}")
            yield JSONRPCResponse(
                id=request.id,
                error=InternalError(
                    message=f"Error processing streaming task: {str(e)}"
                ),
            )

    async def on_cancel_task(self, request: CancelTaskRequest) -> JSONRPCResponse:
        """Handles requests to cancel a task."""
        try:
            task_id = request.params.id
            async with self.lock:
                if task_id in self.tasks:
                    task = self.tasks[task_id]
                    task.status = TaskStatus(state=TaskState.CANCELED)
                    return JSONRPCResponse(id=request.id, result=True)
                return JSONRPCResponse(
                    id=request.id,
                    error=InternalError(message=f"Task {task_id} not found"),
                )
        except Exception as e:
            logger.error(f"Error canceling task: {e}")
            return JSONRPCResponse(
                id=request.id,
                error=InternalError(message=f"Error canceling task: {str(e)}"),
            )

    async def on_set_task_push_notification(
        self, request: SetTaskPushNotificationRequest
    ) -> JSONRPCResponse:
        """Handles requests to configure push notifications for a task."""
        return JSONRPCResponse(id=request.id, result=True)

    async def on_get_task_push_notification(
        self, request: GetTaskPushNotificationRequest
    ) -> JSONRPCResponse:
        """Handles requests to get push notification settings for a task."""
        return JSONRPCResponse(id=request.id, result={})

    async def on_resubscribe_to_task(
        self, request: TaskResubscriptionRequest
    ) -> AsyncIterable[SendTaskStreamingResponse]:
        """Handles requests to resubscribe to a task."""
        task_id = request.params.id
        try:
            async with self.lock:
                if task_id not in self.tasks:
                    yield SendTaskStreamingResponse(
                        id=request.id,
                        error=InternalError(message=f"Task {task_id} not found"),
                    )
                    return

                task = self.tasks[task_id]

            yield SendTaskStreamingResponse(
                id=request.id,
                result=TaskStatusUpdateEvent(
                    id=task_id,
                    status=task.status,
                    final=False,
                ),
            )

            if task.artifacts:
                for artifact in task.artifacts:
                    yield SendTaskStreamingResponse(
                        id=request.id,
                        result=TaskArtifactUpdateEvent(id=task_id, artifact=artifact),
                    )

            yield SendTaskStreamingResponse(
                id=request.id,
                result=TaskStatusUpdateEvent(
                    id=task_id,
                    status=TaskStatus(state=task.status.state),
                    final=True,
                ),
            )

        except Exception as e:
            logger.error(f"Error resubscribing to task: {e}")
            yield SendTaskStreamingResponse(
                id=request.id,
                error=InternalError(message=f"Error resubscribing to task: {str(e)}"),
            )

    async def _process_task(
        self, request: SendTaskRequest, agent: Agent
    ) -> JSONRPCResponse:
        """Processes a task using the specified agent."""
        task_params = request.params
        try:
            query = self._extract_user_query(task_params)
            result_obj = await self._run_agent(agent, query, task_params.sessionId)

            all_messages = await self._extract_messages_from_history(
                result_obj.get("message_history", [])
            )

            result = result_obj["final_response"]
            agent_message = self._create_result_message(result)

            if not all_messages and result:
                all_messages.append(agent_message)

            task_state = self._determine_task_state(result)

            # Create artifacts for any file content
            artifacts = []
            # First, add the main response as an artifact
            artifacts.append(Artifact(parts=agent_message.parts, index=0))

            # Also add any files from the message history
            for idx, msg in enumerate(all_messages, 1):
                for part in msg.parts:
                    if hasattr(part, "type") and part.type == "file":
                        artifacts.append(
                            Artifact(
                                parts=[part],
                                index=idx,
                                name=part.file.name,
                                description=f"File from message {idx}",
                            )
                        )

            task = await self.update_store(
                task_params.id,
                TaskStatus(state=task_state, message=agent_message),
                artifacts,
            )

            await self._update_task_history(
                task_params.id, task_params.message, all_messages
            )

            return SendTaskResponse(id=request.id, result=task)
        except Exception as e:
            logger.error(f"Error processing task: {e}")
            return JSONRPCResponse(
                id=request.id,
                error=InternalError(message=f"Error processing task: {str(e)}"),
            )

    async def _extract_messages_from_history(self, agent_history):
        """Extracts messages from the agent history."""
        all_messages = []
        for message_event in agent_history:
            try:
                if (
                    not isinstance(message_event, dict)
                    or "content" not in message_event
                ):
                    continue

                content = message_event.get("content", {})
                if not isinstance(content, dict):
                    continue

                role = content.get("role", "agent")
                if role not in ["user", "agent"]:
                    role = "agent"

                parts = content.get("parts", [])
                if not parts:
                    continue

                if valid_parts := self._validate_message_parts(parts):
                    agent_message = Message(role=role, parts=valid_parts)
                    all_messages.append(agent_message)
            except Exception as e:
                logger.error(f"Error processing message history: {e}")
        return all_messages

    def _validate_message_parts(self, parts):
        """Validates and formats message parts."""
        valid_parts = []
        for part in parts:
            if isinstance(part, dict):
                if "type" not in part and "text" in part:
                    part["type"] = "text"
                    valid_parts.append(part)
                elif "type" in part:
                    valid_parts.append(part)
        return valid_parts

    def _create_result_message(self, result):
        """Creates a message from the result."""
        text_part = {"type": "text", "text": result}
        return Message(role="agent", parts=[text_part])

    def _determine_task_state(self, result):
        """Determines the task state based on the result."""
        return (
            TaskState.INPUT_REQUIRED
            if "MISSING_INFO:" in result
            else TaskState.COMPLETED
        )

    async def _update_task_history(self, task_id, user_message, agent_messages):
        """Updates the task history."""
        async with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.history = [user_message] + agent_messages

    async def _stream_task_process(
        self, request: SendTaskStreamingRequest, agent: Agent
    ) -> AsyncIterable[SendTaskStreamingResponse]:
        """Processes a task in streaming mode using the specified agent."""
        query = self._extract_user_query(request.params)

        try:
            # Send initial processing status
            processing_text_part = {
                "type": "text",
                "text": "Processing your request...",
            }
            processing_message = Message(role="agent", parts=[processing_text_part])

            # Update the task with the processing message and inform the WORKING state
            await self.update_store(
                request.params.id,
                TaskStatus(state=TaskState.WORKING, message=processing_message),
            )

            yield SendTaskStreamingResponse(
                id=request.id,
                result=TaskStatusUpdateEvent(
                    id=request.params.id,
                    status=TaskStatus(
                        state=TaskState.WORKING,
                        message=processing_message,
                    ),
                    final=False,
                ),
            )

            external_id = request.params.sessionId
            full_response = ""

            final_message = None

            # Check for files in the user message and include them as artifacts
            user_files = []
            for part in request.params.message.parts:
                if (
                    hasattr(part, "type")
                    and part.type == "file"
                    and hasattr(part, "file")
                ):
                    user_files.append(
                        Artifact(
                            parts=[part],
                            index=0,
                            name=part.file.name if part.file.name else "file",
                            description="File from user",
                        )
                    )

            # Send artifacts for any user files
            for artifact in user_files:
                yield SendTaskStreamingResponse(
                    id=request.id,
                    result=TaskArtifactUpdateEvent(
                        id=request.params.id, artifact=artifact
                    ),
                )

            async for chunk in run_agent_stream(
                agent_id=str(agent.id),
                external_id=external_id,
                message=query,
                session_service=session_service,
                artifacts_service=artifacts_service,
                memory_service=memory_service,
                db=self.db,
            ):
                try:
                    chunk_data = json.loads(chunk)

                    if isinstance(chunk_data, dict) and "content" in chunk_data:
                        content = chunk_data.get("content", {})
                        role = content.get("role", "agent")
                        parts = content.get("parts", [])

                        if parts:
                            # Modify to handle file parts as well
                            agent_parts = []
                            for part in parts:
                                # Handle different part types
                                if part.get("type") == "text":
                                    agent_parts.append(part)
                                    full_response += part.get("text", "")
                                elif part.get("inlineData") and part["inlineData"].get(
                                    "data"
                                ):
                                    # Convert inline data to file part
                                    mime_type = part["inlineData"].get(
                                        "mimeType", "application/octet-stream"
                                    )
                                    file_name = f"file_{uuid_pkg.uuid4().hex}{self._get_extension_from_mime(mime_type)}"
                                    file_part = {
                                        "type": "file",
                                        "file": {
                                            "name": file_name,
                                            "mimeType": mime_type,
                                            "bytes": part["inlineData"]["data"],
                                        },
                                    }
                                    agent_parts.append(file_part)

                                    # Also send as artifact
                                    yield SendTaskStreamingResponse(
                                        id=request.id,
                                        result=TaskArtifactUpdateEvent(
                                            id=request.params.id,
                                            artifact=Artifact(
                                                parts=[file_part],
                                                index=0,
                                                name=file_name,
                                                description=f"Generated {mime_type} file",
                                            ),
                                        ),
                                    )

                            if agent_parts:
                                update_message = Message(role=role, parts=agent_parts)
                                final_message = update_message

                            yield SendTaskStreamingResponse(
                                id=request.id,
                                result=TaskStatusUpdateEvent(
                                    id=request.params.id,
                                    status=TaskStatus(
                                        state=TaskState.WORKING,
                                        message=update_message,
                                    ),
                                    final=False,
                                ),
                            )
                except Exception as e:
                    logger.error(f"Error processing chunk: {e}, chunk: {chunk}")
                    continue

            # Determine the final state of the task
            task_state = (
                TaskState.INPUT_REQUIRED
                if "MISSING_INFO:" in full_response
                else TaskState.COMPLETED
            )

            # Create the final response if we don't have one yet
            if not final_message:
                final_text_part = {"type": "text", "text": full_response}
                parts = [final_text_part]
                final_message = Message(role="agent", parts=parts)

            final_artifact = Artifact(parts=final_message.parts, index=0)

            task = await self.update_store(
                request.params.id,
                TaskStatus(state=task_state, message=final_message),
                [final_artifact],
            )

            # Send the final artifact
            yield SendTaskStreamingResponse(
                id=request.id,
                result=TaskArtifactUpdateEvent(
                    id=request.params.id, artifact=final_artifact
                ),
            )

            # Send the final status
            yield SendTaskStreamingResponse(
                id=request.id,
                result=TaskStatusUpdateEvent(
                    id=request.params.id,
                    status=TaskStatus(state=task_state),
                    final=True,
                ),
            )
        except Exception as e:
            logger.error(f"Error streaming task process: {e}")
            yield JSONRPCResponse(
                id=request.id,
                error=InternalError(message=f"Error streaming task process: {str(e)}"),
            )

    def _get_extension_from_mime(self, mime_type: str) -> str:
        """Get a file extension from MIME type."""
        if not mime_type:
            return ""

        mime_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "application/pdf": ".pdf",
            "text/plain": ".txt",
            "text/html": ".html",
            "text/csv": ".csv",
            "application/json": ".json",
            "application/xml": ".xml",
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/vnd.ms-excel": ".xls",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        }

        return mime_map.get(mime_type, "")

    async def update_store(
        self,
        task_id: str,
        status: TaskStatus,
        artifacts: Optional[list[Artifact]] = None,
        update_history: bool = True,
    ) -> Task:
        """Updates the status and artifacts of a task."""
        async with self.lock:
            if task_id not in self.tasks:
                raise ValueError(f"Task {task_id} not found")

            task = self.tasks[task_id]
            task.status = status

            # Add message to history if it exists and update_history is True
            if status.message is not None and update_history:
                if task.history is None:
                    task.history = []
                task.history.append(status.message)

            if artifacts is not None:
                if task.artifacts is None:
                    task.artifacts = []
                task.artifacts.extend(artifacts)

            return task

    def _extract_user_query(self, task_params: TaskSendParams) -> str:
        """Extracts the user query from the task parameters and processes any files."""
        if not task_params.message or not task_params.message.parts:
            raise ValueError("Message or parts are missing in task parameters")

        # Process file parts first
        text_parts = []
        has_files = False
        file_parts = []

        logger.info(
            f"Extracting query from message with {len(task_params.message.parts)} parts"
        )

        # Extract text parts and file parts separately
        for idx, part in enumerate(task_params.message.parts):
            logger.info(
                f"Processing part {idx+1}, type: {getattr(part, 'type', 'unknown')}"
            )
            if hasattr(part, "type"):
                if part.type == "text":
                    logger.info(f"Found text part: '{part.text[:50]}...' (truncated)")
                    text_parts.append(part.text)
                elif part.type == "file":
                    logger.info(
                        f"Found file part: {getattr(getattr(part, 'file', None), 'name', 'unnamed')}"
                    )
                    has_files = True
                    try:
                        processed_file = self._process_file_part(
                            part, task_params.sessionId
                        )
                        if processed_file:
                            file_parts.append(processed_file)
                    except Exception as e:
                        logger.error(f"Error processing file part: {e}")
                        # Continue with other parts even if a file fails
                else:
                    logger.warning(f"Unknown part type: {part.type}")
            else:
                logger.warning(f"Part has no type attribute: {part}")

        # Store the file parts in self for later use
        self._last_processed_files = file_parts if file_parts else None

        # If we have at least one text part, use that as the query
        if text_parts:
            final_query = " ".join(text_parts)
            logger.info(
                f"Final query from text parts: '{final_query[:50]}...' (truncated)"
            )
            return final_query
        # If we only have file parts, create a generic query asking for analysis
        elif has_files:
            logger.info("No text parts, using generic query for file analysis")
            return "Analyze the attached files"
        else:
            logger.error("No supported content parts found in the message")
            raise ValueError("No supported content parts found in the message")

    def _process_file_part(self, part, session_id: str):
        """Processes a file part and saves it to the artifact service.

        Returns:
            dict: Processed file information to pass to agent_runner
        """
        if not hasattr(part, "file") or not part.file:
            logger.warning("File part missing file data")
            return None

        file_data = part.file

        if not file_data.name:
            file_data.name = f"file_{uuid_pkg.uuid4().hex}"

        logger.info(f"Processing file {file_data.name} for session {session_id}")

        if file_data.bytes:
            # Process file data provided as base64 string
            try:
                # Convert base64 to bytes
                logger.info(f"Decoding base64 content for file {file_data.name}")
                file_bytes = base64.b64decode(file_data.bytes)

                # Determine MIME type based on binary content
                mime_type = (
                    file_data.mimeType if hasattr(file_data, "mimeType") else None
                )

                if not mime_type or mime_type == "application/octet-stream":
                    # Detection by byte signature
                    if file_bytes.startswith(b"\xff\xd8\xff"):  # JPEG signature
                        mime_type = "image/jpeg"
                    elif file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG signature
                        mime_type = "image/png"
                    elif file_bytes.startswith(b"GIF87a") or file_bytes.startswith(
                        b"GIF89a"
                    ):  # GIF
                        mime_type = "image/gif"
                    elif file_bytes.startswith(b"%PDF"):  # PDF
                        mime_type = "application/pdf"
                    else:
                        # Fallback to avoid generic type in images
                        if file_data.name.lower().endswith((".jpg", ".jpeg")):
                            mime_type = "image/jpeg"
                        elif file_data.name.lower().endswith(".png"):
                            mime_type = "image/png"
                        elif file_data.name.lower().endswith(".gif"):
                            mime_type = "image/gif"
                        elif file_data.name.lower().endswith(".pdf"):
                            mime_type = "application/pdf"
                        else:
                            mime_type = "application/octet-stream"

                logger.info(
                    f"Decoded file size: {len(file_bytes)} bytes, MIME type: {mime_type}"
                )

                # Split session_id to get app_name and user_id
                parts = session_id.split("_")
                if len(parts) != 2:
                    user_id = session_id
                    app_name = "a2a"
                else:
                    user_id, app_name = parts

                # Create artifact Part
                logger.info(f"Creating artifact Part for file {file_data.name}")
                artifact = Part(inline_data=Blob(mime_type=mime_type, data=file_bytes))

                # Save to artifact service
                logger.info(
                    f"Saving artifact {file_data.name} to {app_name}/{user_id}/{session_id}"
                )
                version = artifacts_service.save_artifact(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=file_data.name,
                    artifact=artifact,
                )

                logger.info(
                    f"Successfully saved file {file_data.name} (version {version}) for session {session_id}"
                )

                # Import the FileData model from the chat schema
                from src.schemas.chat import FileData

                # Create a FileData object instead of a dictionary
                # This is compatible with what agent_runner.py expects
                return FileData(
                    filename=file_data.name,
                    content_type=mime_type,
                    data=file_data.bytes,  # Keep the original base64 format
                )

            except Exception as e:
                logger.error(f"Error processing file data: {str(e)}")
                # Log more details about the error to help with debugging
                import traceback

                logger.error(f"Full traceback: {traceback.format_exc()}")
                raise

        elif file_data.uri:
            # Handling URIs would require additional implementation
            # For now, log that we received a URI but can't process it
            logger.warning(f"File URI references not yet implemented: {file_data.uri}")
            # Future enhancement: fetch the file from the URI and save it
            return None

        return None

    async def _run_agent(self, agent: Agent, query: str, session_id: str) -> dict:
        """Executes the agent to process the user query."""
        try:
            files = getattr(self, "_last_processed_files", None)

            if files:
                logger.info(f"Passing {len(files)} files to run_agent")
                for file_info in files:
                    logger.info(
                        f"File being sent: {file_info.filename} ({file_info.content_type})"
                    )
            else:
                logger.info("No files to pass to run_agent")

            # We call the same function used in the chat API
            return await run_agent(
                agent_id=str(agent.id),
                external_id=session_id,
                message=query,
                session_service=session_service,
                artifacts_service=artifacts_service,
                memory_service=memory_service,
                db=self.db,
                files=files,
            )
        except Exception as e:
            logger.error(f"Error running agent: {e}")
            raise ValueError(f"Error running agent: {str(e)}") from e

    def append_task_history(self, task: Task, history_length: int | None) -> Task:
        """Returns a copy of the task with the history limited to the specified size."""
        # Create a copy of the task
        new_task = task.model_copy()

        # Limit the history if requested
        if history_length is not None and new_task.history:
            if history_length > 0:
                if len(new_task.history) > history_length:
                    user_message = new_task.history[0]
                    recent_messages = (
                        new_task.history[-(history_length - 1) :]
                        if history_length > 1
                        else []
                    )
                    new_task.history = [user_message] + recent_messages
            else:
                new_task.history = []

        return new_task


class A2AService:
    """Service to manage A2A requests and agent cards."""

    def __init__(self, db: Session, task_manager: A2ATaskManager):
        self.db = db
        self.task_manager = task_manager

    async def process_request(
        self, agent_id: UUID, request_body: dict
    ) -> JSONRPCResponse:
        """Processes an A2A request."""
        try:
            request = A2ARequest.validate_python(request_body)

            if isinstance(request, GetTaskRequest):
                return await self.task_manager.on_get_task(request)
            elif isinstance(request, SendTaskRequest):
                return await self.task_manager.on_send_task(request, agent_id)
            elif isinstance(request, SendTaskStreamingRequest):
                return self.task_manager.on_send_task_subscribe(request, agent_id)
            elif isinstance(request, CancelTaskRequest):
                return await self.task_manager.on_cancel_task(request)
            elif isinstance(request, SetTaskPushNotificationRequest):
                return await self.task_manager.on_set_task_push_notification(request)
            elif isinstance(request, GetTaskPushNotificationRequest):
                return await self.task_manager.on_get_task_push_notification(request)
            elif isinstance(request, TaskResubscriptionRequest):
                return self.task_manager.on_resubscribe_to_task(request)
            else:
                logger.warning(f"Unexpected request type: {type(request)}")
                return JSONRPCResponse(
                    id=getattr(request, "id", None),
                    error=InternalError(
                        message=f"Unexpected request type: {type(request)}"
                    ),
                )
        except Exception as e:
            logger.error(f"Error processing A2A request: {e}")
            return JSONRPCResponse(
                id=None,
                error=InternalError(message=f"Error processing A2A request: {str(e)}"),
            )

    def get_agent_card(self, agent_id: UUID) -> AgentCard:
        """Gets the agent card for the specified agent."""
        agent = get_agent(self.db, agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        capabilities = AgentCapabilities(
            streaming=True, pushNotifications=False, stateTransitionHistory=True
        )

        skills = self._get_agent_skills(agent)

        card = AgentCard(
            name=agent.name,
            description=agent.description or "",
            url=f"{settings.API_URL}/api/v1/a2a/{agent_id}",
            provider=AgentProvider(
                organization=settings.ORGANIZATION_NAME,
                url=settings.ORGANIZATION_URL,
            ),
            version=f"{settings.API_VERSION}",
            capabilities=capabilities,
            authentication=AgentAuthentication(
                schemes=["apiKey"],
                credentials="x-api-key",
            ),
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            skills=skills,
        )

        logger.info(f"Generated agent card with {len(skills)} skills")
        return card

    def _get_agent_skills(self, agent: Agent) -> list[AgentSkill]:
        """Extracts the skills of an agent based on its configuration."""
        skills = []

        if self._has_mcp_servers(agent):
            skills.extend(self._get_mcp_server_skills(agent))

        if self._has_custom_tools(agent):
            skills.extend(self._get_custom_tool_skills(agent))

        return skills

    def _has_mcp_servers(self, agent: Agent) -> bool:
        """Checks if the agent has MCP servers configured."""
        return (
            agent.config
            and "mcp_servers" in agent.config
            and agent.config["mcp_servers"]
        )

    def _has_custom_tools(self, agent: Agent) -> bool:
        """Checks if the agent has custom tools configured."""
        return (
            agent.config
            and "custom_tools" in agent.config
            and agent.config["custom_tools"]
        )

    def _get_mcp_server_skills(self, agent: Agent) -> list[AgentSkill]:
        """Gets the skills of the MCP servers configured for the agent."""
        skills = []
        logger.info(
            f"Agent {agent.id} has {len(agent.config['mcp_servers'])} MCP servers configured"
        )

        for mcp_config in agent.config["mcp_servers"]:
            mcp_server_id = mcp_config.get("id")
            if not mcp_server_id:
                logger.warning("MCP server configuration missing ID")
                continue

            mcp_server = get_mcp_server(self.db, mcp_server_id)
            if not mcp_server:
                logger.warning(f"MCP server {mcp_server_id} not found")
                continue

            skills.extend(self._extract_mcp_tool_skills(agent, mcp_server, mcp_config))

        return skills

    def _extract_mcp_tool_skills(
        self, agent: Agent, mcp_server, mcp_config
    ) -> list[AgentSkill]:
        """Extracts skills from MCP tools."""
        skills = []
        mcp_tools = mcp_config.get("tools", [])
        logger.info(f"MCP server {mcp_server.name} has tools: {mcp_tools}")

        for tool_name in mcp_tools:
            tool_info = self._find_tool_info(mcp_server, tool_name)
            skill = self._create_tool_skill(
                agent, tool_name, tool_info, mcp_server.name
            )
            skills.append(skill)
            logger.info(f"Added skill for tool: {tool_name}")

        return skills

    def _find_tool_info(self, mcp_server, tool_name) -> dict:
        """Finds information about a tool in an MCP server."""
        if not hasattr(mcp_server, "tools") or not isinstance(mcp_server.tools, list):
            return None

        for tool in mcp_server.tools:
            if isinstance(tool, dict) and tool.get("id") == tool_name:
                logger.info(f"Found tool info for {tool_name}: {tool}")
                return tool

        return None

    def _create_tool_skill(
        self, agent: Agent, tool_name: str, tool_info: dict, server_name: str
    ) -> AgentSkill:
        """Creates an AgentSkill object based on the tool information."""
        if tool_info:
            return AgentSkill(
                id=tool_info.get("id", f"{agent.id}_{tool_name}"),
                name=tool_info.get("name", tool_name),
                description=tool_info.get("description", f"Tool: {tool_name}"),
                tags=tool_info.get("tags", [server_name, "tool", tool_name]),
                examples=tool_info.get("examples", []),
                inputModes=tool_info.get("inputModes", ["text"]),
                outputModes=tool_info.get("outputModes", ["text"]),
            )
        else:
            return AgentSkill(
                id=f"{agent.id}_{tool_name}",
                name=tool_name,
                description=f"Tool: {tool_name}",
                tags=[server_name, "tool", tool_name],
                examples=[],
                inputModes=["text"],
                outputModes=["text"],
            )

    def _get_custom_tool_skills(self, agent: Agent) -> list[AgentSkill]:
        """Gets the skills of the custom tools of the agent."""
        skills = []
        custom_tools = agent.config["custom_tools"]

        if "http_tools" in custom_tools and custom_tools["http_tools"]:
            logger.info(f"Agent has {len(custom_tools['http_tools'])} HTTP tools")
            for http_tool in custom_tools["http_tools"]:
                skill = AgentSkill(
                    id=f"{agent.id}_http_{http_tool['name']}",
                    name=http_tool["name"],
                    description=http_tool.get(
                        "description", f"HTTP Tool: {http_tool['name']}"
                    ),
                    tags=http_tool.get(
                        "tags", ["http", "custom_tool", http_tool["method"]]
                    ),
                    examples=http_tool.get("examples", []),
                    inputModes=http_tool.get("inputModes", ["text"]),
                    outputModes=http_tool.get("outputModes", ["text"]),
                )
                skills.append(skill)
                logger.info(f"Added skill for HTTP tool: {http_tool['name']}")

        return skills
