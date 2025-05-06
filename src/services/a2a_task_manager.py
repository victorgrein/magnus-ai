import json
import logging
import asyncio
from collections.abc import AsyncIterable
from typing import Any, Dict, Optional, Union, List
from uuid import UUID

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.services.agent_service import (
    get_agent,
    create_agent,
    update_agent,
    delete_agent,
    get_agents_by_client,
)
from src.services.mcp_server_service import get_mcp_server
from src.services.session_service import (
    get_sessions_by_client,
    get_sessions_by_agent,
    get_session_by_id,
    delete_session,
    get_session_events,
)

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
        query = self._extract_user_query(task_params)

        try:
            # Process the query with the agent
            result = await self._run_agent(agent, query, task_params.sessionId)

            # Create the response part
            text_part = {"type": "text", "text": result}
            parts = [text_part]
            agent_message = Message(role="agent", parts=parts)

            # Determine the task state
            task_state = (
                TaskState.INPUT_REQUIRED
                if "MISSING_INFO:" in result
                else TaskState.COMPLETED
            )

            # Update the task in the store
            task = await self.update_store(
                task_params.id,
                TaskStatus(state=task_state, message=agent_message),
                [Artifact(parts=parts, index=0)],
            )

            return SendTaskResponse(id=request.id, result=task)
        except Exception as e:
            logger.error(f"Error processing task: {e}")
            return JSONRPCResponse(
                id=request.id,
                error=InternalError(message=f"Error processing task: {str(e)}"),
            )

    async def _stream_task_process(
        self, request: SendTaskStreamingRequest, agent: Agent
    ) -> AsyncIterable[SendTaskStreamingResponse]:
        """Processes a task in streaming mode using the specified agent."""
        task_params = request.params
        query = self._extract_user_query(task_params)

        try:
            # Send initial processing status
            processing_text_part = {
                "type": "text",
                "text": "Processing your request...",
            }
            processing_message = Message(role="agent", parts=[processing_text_part])

            # Update the task with the processing message and inform the WORKING state
            await self.update_store(
                task_params.id,
                TaskStatus(state=TaskState.WORKING, message=processing_message),
            )

            yield SendTaskStreamingResponse(
                id=request.id,
                result=TaskStatusUpdateEvent(
                    id=task_params.id,
                    status=TaskStatus(
                        state=TaskState.WORKING,
                        message=processing_message,
                    ),
                    final=False,
                ),
            )

            # Collect the chunks of the agent's response
            contact_id = task_params.sessionId
            full_response = ""

            # We use the same streaming function used in the WebSocket
            async for chunk in run_agent_stream(
                agent_id=str(agent.id),
                contact_id=contact_id,
                message=query,
                session_service=session_service,
                artifacts_service=artifacts_service,
                memory_service=memory_service,
                db=self.db,
            ):
                # Send incremental progress updates
                update_text_part = {"type": "text", "text": chunk}
                update_message = Message(role="agent", parts=[update_text_part])

                # Update the task with each intermediate message
                await self.update_store(
                    task_params.id,
                    TaskStatus(state=TaskState.WORKING, message=update_message),
                )

                yield SendTaskStreamingResponse(
                    id=request.id,
                    result=TaskStatusUpdateEvent(
                        id=task_params.id,
                        status=TaskStatus(
                            state=TaskState.WORKING,
                            message=update_message,
                        ),
                        final=False,
                    ),
                )
                full_response += chunk

            # Determine the task state
            task_state = (
                TaskState.INPUT_REQUIRED
                if "MISSING_INFO:" in full_response
                else TaskState.COMPLETED
            )

            # Create the final response part
            final_text_part = {"type": "text", "text": full_response}
            parts = [final_text_part]
            final_message = Message(role="agent", parts=parts)

            # Create the final artifact from the final response
            final_artifact = Artifact(parts=parts, index=0)

            # Update the task in the store with the final response
            task = await self.update_store(
                task_params.id,
                TaskStatus(state=task_state, message=final_message),
                [final_artifact],
            )

            # Send the final artifact
            yield SendTaskStreamingResponse(
                id=request.id,
                result=TaskArtifactUpdateEvent(
                    id=task_params.id, artifact=final_artifact
                ),
            )

            # Send the final status
            yield SendTaskStreamingResponse(
                id=request.id,
                result=TaskStatusUpdateEvent(
                    id=task_params.id,
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

    async def update_store(
        self,
        task_id: str,
        status: TaskStatus,
        artifacts: Optional[list[Artifact]] = None,
    ) -> Task:
        """Updates the status and artifacts of a task."""
        async with self.lock:
            if task_id not in self.tasks:
                raise ValueError(f"Task {task_id} not found")

            task = self.tasks[task_id]
            task.status = status

            # Add message to history if it exists
            if status.message is not None:
                if task.history is None:
                    task.history = []
                task.history.append(status.message)

            if artifacts is not None:
                if task.artifacts is None:
                    task.artifacts = []
                task.artifacts.extend(artifacts)

            return task

    def _extract_user_query(self, task_params: TaskSendParams) -> str:
        """Extracts the user query from the task parameters."""
        if not task_params.message or not task_params.message.parts:
            raise ValueError("Message or parts are missing in task parameters")

        part = task_params.message.parts[0]
        if part.type != "text":
            raise ValueError("Only text parts are supported")

        return part.text

    async def _run_agent(self, agent: Agent, query: str, session_id: str) -> str:
        """Executes the agent to process the user query."""
        try:
            # We use the session_id as contact_id to maintain the conversation continuity
            contact_id = session_id

            # We call the same function used in the chat API
            final_response = await run_agent(
                agent_id=str(agent.id),
                contact_id=contact_id,
                message=query,
                session_service=session_service,
                artifacts_service=artifacts_service,
                memory_service=memory_service,
                db=self.db,
            )

            return final_response
        except Exception as e:
            logger.error(f"Error running agent: {e}")
            raise ValueError(f"Error running agent: {str(e)}")

    def append_task_history(self, task: Task, history_length: int | None) -> Task:
        """Returns a copy of the task with the history limited to the specified size."""
        # Create a copy of the task
        new_task = task.model_copy()

        # Limit the history if requested
        if history_length is not None:
            if history_length > 0:
                new_task.history = (
                    new_task.history[-history_length:] if new_task.history else []
                )
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

        # Build the agent card based on the agent's information
        capabilities = AgentCapabilities(streaming=True)

        # List to store all skills
        skills = []

        # Check if the agent has MCP servers configured
        if (
            agent.config
            and "mcp_servers" in agent.config
            and agent.config["mcp_servers"]
        ):
            logger.info(
                f"Agent {agent_id} has {len(agent.config['mcp_servers'])} MCP servers configured"
            )

            for mcp_config in agent.config["mcp_servers"]:
                # Get the MCP server
                mcp_server_id = mcp_config.get("id")
                if not mcp_server_id:
                    logger.warning("MCP server configuration missing ID")
                    continue

                logger.info(f"Processing MCP server: {mcp_server_id}")
                mcp_server = get_mcp_server(self.db, mcp_server_id)
                if not mcp_server:
                    logger.warning(f"MCP server {mcp_server_id} not found")
                    continue

                # Get the available tools in the MCP server
                mcp_tools = mcp_config.get("tools", [])
                logger.info(f"MCP server {mcp_server.name} has tools: {mcp_tools}")

                # Add server tools as skills
                for tool_name in mcp_tools:
                    logger.info(f"Processing tool: {tool_name}")

                    tool_info = None
                    if hasattr(mcp_server, "tools") and isinstance(
                        mcp_server.tools, list
                    ):
                        for tool in mcp_server.tools:
                            if isinstance(tool, dict) and tool.get("id") == tool_name:
                                tool_info = tool
                                logger.info(
                                    f"Found tool info for {tool_name}: {tool_info}"
                                )
                                break

                    if tool_info:
                        # Use the information from the tool
                        skill = AgentSkill(
                            id=tool_info.get("id", f"{agent.id}_{tool_name}"),
                            name=tool_info.get("name", tool_name),
                            description=tool_info.get(
                                "description", f"Tool: {tool_name}"
                            ),
                            tags=tool_info.get(
                                "tags", [mcp_server.name, "tool", tool_name]
                            ),
                            examples=tool_info.get("examples", []),
                            inputModes=tool_info.get("inputModes", ["text"]),
                            outputModes=tool_info.get("outputModes", ["text"]),
                        )
                    else:
                        # Default skill if tool info not found
                        skill = AgentSkill(
                            id=f"{agent.id}_{tool_name}",
                            name=tool_name,
                            description=f"Tool: {tool_name}",
                            tags=[mcp_server.name, "tool", tool_name],
                            examples=[],
                            inputModes=["text"],
                            outputModes=["text"],
                        )

                    skills.append(skill)
                    logger.info(f"Added skill for tool: {tool_name}")

        # Check custom tools
        if (
            agent.config
            and "custom_tools" in agent.config
            and agent.config["custom_tools"]
        ):
            custom_tools = agent.config["custom_tools"]

            # Check HTTP tools
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
