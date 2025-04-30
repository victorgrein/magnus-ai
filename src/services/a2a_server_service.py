"""
Server A2A and task manager for the A2A protocol.

This module implements a JSON-RPC compatible server for the A2A protocol,
that manages agent tasks, streaming events and push notifications.
"""

import json
import logging
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Optional,
    AsyncGenerator,
    Union,
    AsyncIterable,
)
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse, Response
from sqlalchemy.orm import Session

from src.schemas.a2a.types import A2ARequest
from src.services.a2a_integration_service import (
    AgentRunnerAdapter,
    StreamingServiceAdapter,
)
from src.services.session_service import get_session_events
from src.services.redis_cache_service import RedisCacheService
from src.schemas.a2a.types import (
    SendTaskRequest,
    SendTaskStreamingRequest,
    GetTaskRequest,
    CancelTaskRequest,
    SetTaskPushNotificationRequest,
    GetTaskPushNotificationRequest,
    TaskResubscriptionRequest,
)

logger = logging.getLogger(__name__)


class A2ATaskManager:
    """
    Task manager for the A2A protocol.

    This class manages the lifecycle of tasks, including:
    - Task execution
    - Streaming of events
    - Push notifications
    - Status querying
    - Cancellation
    """

    def __init__(
        self,
        redis_cache: RedisCacheService,
        agent_runner: AgentRunnerAdapter,
        streaming_service: StreamingServiceAdapter,
        push_notification_service: Any = None,
    ):
        """
        Initialize the task manager.

        Args:
            redis_cache: Cache service for storing task data
            agent_runner: Adapter for agent execution
            streaming_service: Adapter for event streaming
            push_notification_service: Service for sending push notifications
        """
        self.cache = redis_cache
        self.agent_runner = agent_runner
        self.streaming_service = streaming_service
        self.push_notification_service = push_notification_service
        self._running_tasks = {}

    async def on_send_task(
        self,
        task_id: str,
        agent_id: str,
        message: Dict[str, Any],
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        input_mode: str = "text",
        output_modes: List[str] = ["text"],
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Process a request to send a task.

        Args:
            task_id: Task ID
            agent_id: Agent ID
            message: User message
            session_id: Session ID (optional)
            metadata: Additional metadata (optional)
            input_mode: Input mode (text, JSON, etc.)
            output_modes: Supported output modes
            db: Database session

        Returns:
            Response with task result
        """
        if not session_id:
            session_id = f"{task_id}_{agent_id}"

        if not metadata:
            metadata = {}

        # Update status to "submitted"
        task_data = {
            "id": task_id,
            "sessionId": session_id,
            "status": {
                "state": "submitted",
                "timestamp": datetime.now().isoformat(),
                "message": None,
                "error": None,
            },
            "artifacts": [],
            "history": [],
            "metadata": metadata,
        }

        # Store initial task data
        await self.cache.set(f"task:{task_id}", task_data)

        # Check for push notification configurations
        push_config = await self.cache.get(f"task:{task_id}:push")
        if push_config and self.push_notification_service:
            # Send initial notification
            await self.push_notification_service.send_notification(
                url=push_config["url"],
                task_id=task_id,
                state="submitted",
                headers=push_config.get("headers", {}),
            )

        try:
            # Update status to "running"
            task_data["status"].update(
                {"state": "running", "timestamp": datetime.now().isoformat()}
            )
            await self.cache.set(f"task:{task_id}", task_data)

            # Notify "running" state
            if push_config and self.push_notification_service:
                await self.push_notification_service.send_notification(
                    url=push_config["url"],
                    task_id=task_id,
                    state="running",
                    headers=push_config.get("headers", {}),
                )

            # Extract user message
            user_message = None
            try:
                user_message = message["parts"][0]["text"]
            except (KeyError, IndexError):
                user_message = ""

            # Execute the agent
            response = await self.agent_runner.run_agent(
                agent_id=agent_id,
                task_id=task_id,
                message=user_message,
                session_id=session_id,
                db=db,
            )

            # Check if the response is a dictionary (error) or a string (success)
            if isinstance(response, dict) and response.get("status") == "error":
                # Error response
                final_response = f"Error: {response.get('error', 'Unknown error')}"

                # Update status to "failed"
                task_data["status"].update(
                    {
                        "state": "failed",
                        "timestamp": datetime.now().isoformat(),
                        "error": {
                            "code": "AGENT_EXECUTION_ERROR",
                            "message": response.get("error", "Unknown error"),
                        },
                        "message": {
                            "role": "system",
                            "parts": [{"type": "text", "text": final_response}],
                        },
                    }
                )

                # Notify "failed" state
                if push_config and self.push_notification_service:
                    await self.push_notification_service.send_notification(
                        url=push_config["url"],
                        task_id=task_id,
                        state="failed",
                        message={
                            "role": "system",
                            "parts": [{"type": "text", "text": final_response}],
                        },
                        headers=push_config.get("headers", {}),
                    )
            else:
                # Success response
                final_response = (
                    response.get("content") if isinstance(response, dict) else response
                )

                # Update status to "completed"
                task_data["status"].update(
                    {
                        "state": "completed",
                        "timestamp": datetime.now().isoformat(),
                        "message": {
                            "role": "agent",
                            "parts": [{"type": "text", "text": final_response}],
                        },
                    }
                )

                # Add artifacts
                if final_response:
                    task_data["artifacts"].append(
                        {
                            "type": "text",
                            "content": final_response,
                            "metadata": {
                                "generated_at": datetime.now().isoformat(),
                                "content_type": "text/plain",
                            },
                        }
                    )

                # Add history of messages
                history_length = metadata.get("historyLength", 50)
                try:
                    history_messages = get_session_events(
                        self.agent_runner.session_service, session_id
                    )
                    history_messages = history_messages[-history_length:]

                    formatted_history = []
                    for event in history_messages:
                        if event.content and event.content.parts:
                            role = (
                                "agent"
                                if event.content.role == "model"
                                else event.content.role
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

                    task_data["history"] = formatted_history
                except Exception as e:
                    logger.error(f"Error processing history: {str(e)}")

                # Notify "completed" state
                if push_config and self.push_notification_service:
                    await self.push_notification_service.send_notification(
                        url=push_config["url"],
                        task_id=task_id,
                        state="completed",
                        message={
                            "role": "agent",
                            "parts": [{"type": "text", "text": final_response}],
                        },
                        headers=push_config.get("headers", {}),
                    )

        except Exception as e:
            logger.error(f"Error executing task {task_id}: {str(e)}")

            # Update status to "failed"
            task_data["status"].update(
                {
                    "state": "failed",
                    "timestamp": datetime.now().isoformat(),
                    "error": {"code": "AGENT_EXECUTION_ERROR", "message": str(e)},
                }
            )

            # Notify "failed" state
            if push_config and self.push_notification_service:
                await self.push_notification_service.send_notification(
                    url=push_config["url"],
                    task_id=task_id,
                    state="failed",
                    message={
                        "role": "system",
                        "parts": [{"type": "text", "text": str(e)}],
                    },
                    headers=push_config.get("headers", {}),
                )

        # Store final result
        await self.cache.set(f"task:{task_id}", task_data)
        return task_data

    async def on_send_task_subscribe(
        self,
        task_id: str,
        agent_id: str,
        message: Dict[str, Any],
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        input_mode: str = "text",
        output_modes: List[str] = ["text"],
        db: Optional[Session] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Process a request to send a task with streaming.

        Args:
            task_id: Task ID
            agent_id: Agent ID
            message: User message
            session_id: Session ID (optional)
            metadata: Additional metadata (optional)
            input_mode: Input mode (text, JSON, etc.)
            output_modes: Supported output modes
            db: Database session

        Yields:
            Streaming events in SSE (Server-Sent Events) format
        """
        if not session_id:
            session_id = f"{task_id}_{agent_id}"

        if not metadata:
            metadata = {}

        # Extract user message
        user_message = ""
        try:
            user_message = message["parts"][0]["text"]
        except (KeyError, IndexError):
            pass

        # Generate streaming events
        async for event in self.streaming_service.stream_response(
            agent_id=agent_id,
            task_id=task_id,
            message=user_message,
            session_id=session_id,
            db=db,
        ):
            yield event

    async def on_get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Query the status of a task by ID.

        Args:
            task_id: Task ID

        Returns:
            Current task status

        Raises:
            Exception: If the task is not found
        """
        task_data = await self.cache.get(f"task:{task_id}")
        if not task_data:
            raise Exception(f"Task {task_id} not found")
        return task_data

    async def on_cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel a running task.

        Args:
            task_id: Task ID to be cancelled

        Returns:
            Task status after cancellation

        Raises:
            Exception: If the task is not found or cannot be cancelled
        """
        task_data = await self.cache.get(f"task:{task_id}")
        if not task_data:
            raise Exception(f"Task {task_id} not found")

        # Check if the task is in a state that can be cancelled
        current_state = task_data["status"]["state"]
        if current_state not in ["submitted", "running"]:
            raise Exception(f"Cannot cancel task in {current_state} state")

        # Cancel the task in the runner if it is running
        running_task = self._running_tasks.get(task_id)
        if running_task:
            # Try to cancel the running task
            if hasattr(running_task, "cancel"):
                running_task.cancel()

        # Update status to "cancelled"
        task_data["status"].update(
            {
                "state": "cancelled",
                "timestamp": datetime.now().isoformat(),
                "message": {
                    "role": "system",
                    "parts": [{"type": "text", "text": "Task cancelled by user"}],
                },
            }
        )

        # Update cache
        await self.cache.set(f"task:{task_id}", task_data)

        # Send push notification if configured
        push_config = await self.cache.get(f"task:{task_id}:push")
        if push_config and self.push_notification_service:
            await self.push_notification_service.send_notification(
                url=push_config["url"],
                task_id=task_id,
                state="cancelled",
                message={
                    "role": "system",
                    "parts": [{"type": "text", "text": "Task cancelled by user"}],
                },
                headers=push_config.get("headers", {}),
            )

        return task_data

    async def on_set_task_push_notification(
        self, task_id: str, notification_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Configure push notifications for a task.

        Args:
            task_id: Task ID
            notification_config: Notification configuration (URL and headers)

        Returns:
            Updated configuration
        """
        # Validate configuration
        url = notification_config.get("url")
        if not url:
            raise ValueError("Push notification URL is required")

        headers = notification_config.get("headers", {})

        # Store configuration
        config = {"url": url, "headers": headers}
        await self.cache.set(f"task:{task_id}:push", config)

        return config

    async def on_get_task_push_notification(self, task_id: str) -> Dict[str, Any]:
        """
        Get the push notification configuration for a task.

        Args:
            task_id: Task ID

        Returns:
            Push notification configuration

        Raises:
            Exception: If there is no configuration for the task
        """
        config = await self.cache.get(f"task:{task_id}:push")
        if not config:
            raise Exception(f"No push notification configuration for task {task_id}")
        return config


class A2AServer:
    """
    A2A server compatible with JSON-RPC 2.0.

    This class processes JSON-RPC requests and forwards them to
    the appropriate handlers in the A2ATaskManager.
    """

    def __init__(self, task_manager: A2ATaskManager, agent_card=None):
        """
        Initialize the A2A server.

        Args:
            task_manager: Task manager
            agent_card: Agent card information
        """
        self.task_manager = task_manager
        self.agent_card = agent_card

    async def process_request(
        self,
        request: Request,
        agent_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Union[Response, JSONResponse, StreamingResponse]:
        """
        Process a JSON-RPC request.

        Args:
            request: HTTP request
            agent_id: Optional agent ID to inject into the request
            db: Database session

        Returns:
            Appropriate response (JSON or Streaming)
        """
        try:
            # Try to parse the JSON payload
            try:
                logger.info("Starting JSON-RPC request processing")
                body = await request.json()
                logger.info(f"Received JSON data: {json.dumps(body)}")
                method = body.get("method", "unknown")

                # Validate the request using the A2A validator
                json_rpc_request = A2ARequest.validate_python(body)

                original_db = self.task_manager.db
                try:
                    # Set the db temporarily
                    if db is not None:
                        self.task_manager.db = db

                    # Process the request
                    if isinstance(json_rpc_request, SendTaskRequest):
                        json_rpc_request.params.agentId = agent_id
                        result = await self.task_manager.on_send_task(json_rpc_request)
                    elif isinstance(json_rpc_request, SendTaskStreamingRequest):
                        json_rpc_request.params.agentId = agent_id
                        result = await self.task_manager.on_send_task_subscribe(
                            json_rpc_request
                        )
                    elif isinstance(json_rpc_request, GetTaskRequest):
                        result = await self.task_manager.on_get_task(json_rpc_request)
                    elif isinstance(json_rpc_request, CancelTaskRequest):
                        result = await self.task_manager.on_cancel_task(
                            json_rpc_request
                        )
                    elif isinstance(json_rpc_request, SetTaskPushNotificationRequest):
                        result = await self.task_manager.on_set_task_push_notification(
                            json_rpc_request
                        )
                    elif isinstance(json_rpc_request, GetTaskPushNotificationRequest):
                        result = await self.task_manager.on_get_task_push_notification(
                            json_rpc_request
                        )
                    elif isinstance(json_rpc_request, TaskResubscriptionRequest):
                        result = await self.task_manager.on_resubscribe_to_task(
                            json_rpc_request
                        )
                    else:
                        logger.warning(
                            f"[SERVER] Request type not supported: {type(json_rpc_request)}"
                        )
                        return JSONResponse(
                            status_code=400,
                            content={
                                "jsonrpc": "2.0",
                                "id": body.get("id"),
                                "error": {
                                    "code": -32601,
                                    "message": "Method not found",
                                    "data": {
                                        "detail": f"Method not supported: {method}"
                                    },
                                },
                            },
                        )
                finally:
                    # Restore the original db
                    self.task_manager.db = original_db

                # Create appropriate response
                return self._create_response(result)

            except json.JSONDecodeError as e:
                # Error parsing JSON
                logger.error(f"Error parsing JSON request: {str(e)}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": "Parse error",
                            "data": {"detail": str(e)},
                        },
                    },
                )
            except Exception as e:
                # Other validation errors
                logger.error(f"Error validating request: {str(e)}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "jsonrpc": "2.0",
                        "id": body.get("id") if "body" in locals() else None,
                        "error": {
                            "code": -32600,
                            "message": "Invalid Request",
                            "data": {"detail": str(e)},
                        },
                    },
                )

        except Exception as e:
            logger.error(f"Error processing JSON-RPC request: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": {"detail": str(e)},
                    },
                },
            )

    def _create_response(self, result: Any) -> Union[JSONResponse, StreamingResponse]:
        """
        Create appropriate response based on result type.

        Args:
            result: Result from task manager

        Returns:
            JSON or streaming response
        """
        if isinstance(result, AsyncIterable):
            # Result in streaming (SSE)
            async def event_generator():
                async for item in result:
                    if hasattr(item, "model_dump_json"):
                        yield {"data": item.model_dump_json(exclude_none=True)}
                    else:
                        yield {"data": json.dumps(item)}

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        elif hasattr(result, "model_dump"):
            # Result is a Pydantic object
            return JSONResponse(result.model_dump(exclude_none=True))

        else:
            # Result is a dictionary or other simple type
            return JSONResponse(result)

    async def get_agent_card(
        self, request: Request, db: Optional[Session] = None
    ) -> JSONResponse:
        """
        Get the agent card.

        Args:
            request: HTTP request
            db: Database session

        Returns:
            Agent card as JSON
        """
        if not self.agent_card:
            logger.error("Agent card not configured")
            return JSONResponse(
                status_code=404, content={"error": "Agent card not configured"}
            )

        # If there is db, set it temporarily in the task_manager
        if db and hasattr(self.task_manager, "db"):
            original_db = self.task_manager.db
            try:
                self.task_manager.db = db

                # If it's a Pydantic object, convert to dictionary
                if hasattr(self.agent_card, "model_dump"):
                    return JSONResponse(self.agent_card.model_dump(exclude_none=True))
                else:
                    return JSONResponse(self.agent_card)
            finally:
                # Restore the original db
                self.task_manager.db = original_db
        else:
            # If it's a Pydantic object, convert to dictionary
            if hasattr(self.agent_card, "model_dump"):
                return JSONResponse(self.agent_card.model_dump(exclude_none=True))
            else:
                return JSONResponse(self.agent_card)
