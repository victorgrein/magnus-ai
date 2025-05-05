"""
A2A Integration Service.

This service provides adapters to integrate existing services with the A2A protocol.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, AsyncIterable

from src.schemas.a2a import (
    AgentCard,
    AgentCapabilities,
    AgentProvider,
    Artifact,
    Message,
    TaskArtifactUpdateEvent,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)

logger = logging.getLogger(__name__)


class AgentRunnerAdapter:
    """
    Adapter for integrating the existing agent runner with the A2A protocol.
    """

    def __init__(
        self,
        agent_runner_func,
        session_service=None,
        artifacts_service=None,
        memory_service=None,
        db=None,
    ):
        """
        Initialize the adapter.

        Args:
            agent_runner_func: The agent runner function (e.g., run_agent)
            session_service: Session service for message history
            artifacts_service: Artifacts service for artifact history
            memory_service: Memory service for agent memory
            db: Database session
        """
        self.agent_runner_func = agent_runner_func
        self.session_service = session_service
        self.artifacts_service = artifacts_service
        self.memory_service = memory_service
        self.db = db

    async def get_supported_modes(self) -> List[str]:
        """
        Get the supported output modes for the agent.

        Returns:
            List of supported output modes
        """
        # Default modes, can be extended based on agent configuration
        return ["text", "application/json"]

    async def run_agent(
        self,
        agent_id: str,
        message: str,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        db=None,
    ) -> Dict[str, Any]:
        """
        Run the agent with the given message.

        Args:
            agent_id: ID of the agent to run
            message: User message to process
            session_id: Optional session ID for conversation context
            task_id: Optional task ID for tracking
            db: Database session

        Returns:
            Dictionary with the agent's response
        """

        try:
            # Use the existing agent runner function
            # Usar o session_id fornecido, ou gerar um novo
            session_id = session_id or str(uuid.uuid4())
            task_id = task_id or str(uuid.uuid4())

            # Use the provided db or fallback to self.db
            db_session = db if db is not None else self.db

            response_text = await self.agent_runner_func(
                agent_id=agent_id,
                contact_id=task_id,
                message=message,
                session_service=self.session_service,
                artifacts_service=self.artifacts_service,
                memory_service=self.memory_service,
                db=db_session,
                session_id=session_id,
            )

            # Format the response to include both the A2A-compatible message
            # and the artifact format to match the Google A2A implementation
            # Nota: O formato dos artifacts é simplificado para compatibilidade com Google A2A
            message_obj = {
                "role": "agent",
                "parts": [{"type": "text", "text": response_text}],
            }

            # Formato de artefato compatível com Google A2A
            artifact_obj = {
                "parts": [{"type": "text", "text": response_text}],
                "index": 0,
            }

            return {
                "status": "success",
                "content": response_text,
                "session_id": session_id,
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "message": message_obj,
                "artifact": artifact_obj,
            }

        except Exception as e:
            logger.error(f"[AGENT-RUNNER] Error running agent: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "session_id": session_id,
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "message": {
                    "role": "agent",
                    "parts": [{"type": "text", "text": f"Error: {str(e)}"}],
                },
            }

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.

        Args:
            task_id: ID of the task to cancel

        Returns:
            True if successfully canceled, False otherwise
        """
        # Currently, the agent runner doesn't support cancellation
        # This is a placeholder for future implementation
        logger.warning(f"Task cancellation not implemented for task {task_id}")
        return False


class StreamingServiceAdapter:
    """
    Adapter for integrating the existing streaming service with the A2A protocol.
    """

    def __init__(self, streaming_service):
        """
        Initialize the adapter.

        Args:
            streaming_service: The streaming service instance
        """
        self.streaming_service = streaming_service

    async def stream_agent_response(
        self,
        agent_id: str,
        message: str,
        api_key: str,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        db=None,
    ) -> AsyncIterable[str]:
        """
        Stream the agent's response as A2A events.

        Args:
            agent_id: ID of the agent
            message: User message to process
            api_key: API key for authentication
            session_id: Optional session ID for conversation context
            task_id: Optional task ID for tracking
            db: Database session

        Yields:
            A2A event objects as JSON strings for SSE (Server-Sent Events)
        """
        task_id = task_id or str(uuid.uuid4())
        logger.info(f"Starting streaming response for task {task_id}")

        # Set working status event
        working_status = TaskStatus(
            state="working",
            timestamp=datetime.now(),
            message=Message(
                role="agent", parts=[TextPart(text="Processing your request...")]
            ),
        )

        status_event = TaskStatusUpdateEvent(
            id=task_id, status=working_status, final=False
        )
        yield json.dumps(status_event.model_dump())

        content_buffer = ""
        final_sent = False
        has_error = False

        # Stream from the existing streaming service
        try:
            logger.info(f"Setting up streaming for agent {agent_id}, task {task_id}")
            # To streaming, we use task_id as contact_id
            contact_id = task_id

            last_event_time = datetime.now()
            heartbeat_interval = 20

            async for event in self.streaming_service.send_task_streaming(
                agent_id=agent_id,
                api_key=api_key,
                message=message,
                contact_id=contact_id,
                session_id=session_id,
                db=db,
            ):
                last_event_time = datetime.now()

                # Process the streaming event format
                event_data = event.get("data", "{}")
                try:
                    logger.info(f"Processing event data: {event_data[:100]}...")
                    data = json.loads(event_data)

                    # Extract content
                    if "delta" in data and data["delta"].get("content"):
                        content = data["delta"]["content"]
                        content_buffer += content
                        logger.info(f"Received content chunk: {content[:50]}...")

                        # Create artifact update event
                        artifact = Artifact(
                            name="response",
                            parts=[TextPart(text=content)],
                            index=0,
                            append=True,
                            lastChunk=False,
                        )

                        artifact_event = TaskArtifactUpdateEvent(
                            id=task_id, artifact=artifact
                        )
                        yield json.dumps(artifact_event.model_dump())

                    # Check if final event
                    if data.get("done", False) and not final_sent:
                        logger.info(f"Received final event for task {task_id}")
                        # Create completed status event
                        completed_status = TaskStatus(
                            state="completed",
                            timestamp=datetime.now(),
                            message=Message(
                                role="agent",
                                parts=[
                                    TextPart(text=content_buffer or "Task completed")
                                ],
                            ),
                        )

                        # Final artifact with full content
                        final_artifact = Artifact(
                            name="response",
                            parts=[TextPart(text=content_buffer)],
                            index=0,
                            append=False,
                            lastChunk=True,
                        )

                        # Send the final artifact
                        final_artifact_event = TaskArtifactUpdateEvent(
                            id=task_id, artifact=final_artifact
                        )

                        yield json.dumps(final_artifact_event.model_dump())

                        # Send the completed status
                        final_status_event = TaskStatusUpdateEvent(
                            id=task_id,
                            status=completed_status,
                            final=True,
                        )

                        yield json.dumps(final_status_event.model_dump())

                        final_sent = True

                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Received non-JSON event data: {e}. Data: {event_data[:100]}..."
                    )
                    # Handle non-JSON events - simply add to buffer as text
                    if isinstance(event_data, str):
                        content_buffer += event_data

                        # Create artifact update event
                        artifact = Artifact(
                            name="response",
                            parts=[TextPart(text=event_data)],
                            index=0,
                            append=True,
                            lastChunk=False,
                        )

                        artifact_event = TaskArtifactUpdateEvent(
                            id=task_id, artifact=artifact
                        )

                        yield json.dumps(artifact_event.model_dump())
                    elif isinstance(event_data, dict):
                        # Try to extract text from the dictionary
                        text_value = str(event_data)
                        content_buffer += text_value

                        artifact = Artifact(
                            name="response",
                            parts=[TextPart(text=text_value)],
                            index=0,
                            append=True,
                            lastChunk=False,
                        )

                        artifact_event = TaskArtifactUpdateEvent(
                            id=task_id, artifact=artifact
                        )

                        yield json.dumps(artifact_event.model_dump())

                # Send heartbeat/keep-alive to keep the SSE connection open
                now = datetime.now()
                if (now - last_event_time).total_seconds() > heartbeat_interval:
                    logger.info(f"Sending heartbeat for task {task_id}")
                    # Sending keep-alive event as a "working" status event
                    working_heartbeat = TaskStatus(
                        state="working",
                        timestamp=now,
                        message=Message(
                            role="agent", parts=[TextPart(text="Still processing...")]
                        ),
                    )
                    heartbeat_event = TaskStatusUpdateEvent(
                        id=task_id, status=working_heartbeat, final=False
                    )
                    yield json.dumps(heartbeat_event.model_dump())
                    last_event_time = now

            # Ensure we send a final event if not already sent
            if not final_sent:
                logger.info(
                    f"Stream completed for task {task_id}, sending final status"
                )
                # Create completed status event
                completed_status = TaskStatus(
                    state="completed",
                    timestamp=datetime.now(),
                    message=Message(
                        role="agent",
                        parts=[TextPart(text=content_buffer or "Task completed")],
                    ),
                )

                # Send the completed status
                final_event = TaskStatusUpdateEvent(
                    id=task_id, status=completed_status, final=True
                )
                yield json.dumps(final_event.model_dump())

        except Exception as e:
            has_error = True
            logger.error(f"Error in streaming for task {task_id}: {e}", exc_info=True)

            # Create failed status event
            failed_status = TaskStatus(
                state="failed",
                timestamp=datetime.now(),
                message=Message(
                    role="agent",
                    parts=[
                        TextPart(
                            text=f"Error during streaming: {str(e)}. Partial response: {content_buffer[:200] if content_buffer else 'No content received'}"
                        )
                    ],
                ),
            )

            error_event = TaskStatusUpdateEvent(
                id=task_id, status=failed_status, final=True
            )
            yield json.dumps(error_event.model_dump())

        finally:
            # Ensure we send a final event to properly close the connection
            if not final_sent and not has_error:
                logger.info(f"Stream finalizing for task {task_id} via finally block")
                try:
                    # Create completed status event
                    completed_status = TaskStatus(
                        state="completed",
                        timestamp=datetime.now(),
                        message=Message(
                            role="agent",
                            parts=[
                                TextPart(
                                    text=content_buffer or "Task completed (forced end)"
                                )
                            ],
                        ),
                    )

                    # Send the completed status
                    final_event = TaskStatusUpdateEvent(
                        id=task_id, status=completed_status, final=True
                    )
                    yield json.dumps(final_event.model_dump())
                except Exception as final_error:
                    logger.error(
                        f"Error sending final event in finally block: {final_error}"
                    )

            logger.info(f"Streaming completed for task {task_id}")


def create_agent_card_from_agent(agent, db) -> AgentCard:
    """
    Create an A2A agent card from an agent model.

    Args:
        agent: The agent model from the database
        db: Database session

    Returns:
        A2A AgentCard object
    """
    import os
    from src.api.agent_routes import format_agent_tools
    import asyncio

    # Extract agent configuration
    agent_config = agent.config
    has_streaming = True  # Assuming streaming is always supported
    has_push = True  # Assuming push notifications are supported

    # Format tools as skills
    try:
        # We use a different approach to handle the asynchronous function
        mcp_servers = agent_config.get("mcp_servers", [])

        # We create a new thread to execute the asynchronous function
        import concurrent.futures

        def run_async(coro):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(coro)
            loop.close()
            return result

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_async, format_agent_tools(mcp_servers, db))
            skills = future.result()
    except Exception as e:
        logger.error(f"Error formatting agent tools: {e}")
        skills = []

    # Create agent card
    return AgentCard(
        name=agent.name,
        description=agent.description,
        url=f"{os.getenv('API_URL', '')}/api/v1/a2a/{agent.id}",
        provider=AgentProvider(
            organization=os.getenv("ORGANIZATION_NAME", ""),
            url=os.getenv("ORGANIZATION_URL", ""),
        ),
        version=os.getenv("API_VERSION", "1.0.0"),
        capabilities=AgentCapabilities(
            streaming=has_streaming,
            pushNotifications=has_push,
            stateTransitionHistory=True,
        ),
        authentication={
            "schemes": ["apiKey"],
            "credentials": "x-api-key",
        },
        defaultInputModes=["text", "application/json"],
        defaultOutputModes=["text", "application/json"],
        skills=skills,
    )
