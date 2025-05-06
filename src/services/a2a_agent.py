from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai.types import Content, Part
from typing import AsyncGenerator, Dict, Any, Optional
import json
import asyncio
import time
import logging

from src.schemas.a2a_types import (
    GetTaskRequest,
    SendTaskRequest,
    SendTaskStreamingRequest,
    Message,
    TextPart,
    TaskState,
    JSONRPCRequest,
)

import httpx

from uuid import uuid4

logger = logging.getLogger(__name__)


class A2ACustomAgent(BaseAgent):
    """
    Custom agent that implements the A2A protocol directly.

    This agent implements the interaction with an external A2A service.
    """

    # Field declarations for Pydantic
    agent_card_url: str
    api_key: Optional[str]
    poll_interval: float
    max_wait_time: int
    timeout: int
    streaming: bool
    base_url: Optional[str] = None

    def __init__(
        self,
        name: str,
        agent_card_url: str,
        api_key: Optional[str] = None,
        poll_interval: float = 1.0,
        max_wait_time: int = 60,
        timeout: int = 300,
        streaming: bool = True,
        **kwargs,
    ):
        """
        Initialize the A2A agent.

        Args:
            name: Agent name
            agent_card_url: A2A agent card URL
            api_key: API key for authentication
            poll_interval: Status check interval (seconds)
            max_wait_time: Maximum wait time for a task (seconds)
            timeout: Maximum execution time (seconds)
            streaming: Whether to use streaming mode
        """
        # Get base URL by removing agent.json if present
        derived_base_url = agent_card_url
        if "/.well-known/agent.json" in derived_base_url:
            derived_base_url = derived_base_url.split("/.well-known/agent.json")[0]

        # Initialize base class with all fields including base_url
        super().__init__(
            name=name,
            agent_card_url=agent_card_url,
            api_key=api_key,
            poll_interval=poll_interval,
            max_wait_time=max_wait_time,
            timeout=timeout,
            streaming=streaming,
            base_url=derived_base_url,
            **kwargs,
        )

        logger.info(f"A2A agent initialized for URL: {agent_card_url}")

        # Default headers
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["x-api-key"] = api_key

    async def _send_jsonrpc_request(self, request: JSONRPCRequest) -> Dict[str, Any]:
        """
        Send a JSON-RPC request to the A2A endpoint.

        Args:
            request: The JSON-RPC request object

        Returns:
            Dict containing the response
        """
        try:
            async with httpx.AsyncClient() as client:
                logger.debug(
                    f"Sending request to {self.base_url}: {request.model_dump()}"
                )
                response = await client.post(
                    self.base_url,
                    json=request.model_dump(),
                    headers=self.headers,
                    timeout=30,
                )

                response.raise_for_status()
                response_data = response.json()
                logger.debug(f"Received response: {response_data}")

                # Check for JSON-RPC errors
                if "error" in response_data and response_data["error"]:
                    error_msg = response_data["error"].get("message", "Unknown error")
                    error_code = response_data["error"].get("code", -1)
                    logger.error(f"JSON-RPC error {error_code}: {error_msg}")
                    raise ValueError(f"A2A server error: {error_msg}")

                return response_data
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e}")
            raise ValueError(f"HTTP error {e.response.status_code}: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise ValueError(f"Request error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise ValueError(f"Invalid JSON response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise ValueError(f"Error communicating with A2A server: {str(e)}")

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Implementation of the A2A protocol according to the Google ADK documentation.

        This method follows the pattern of implementing custom agents,
        sending the user's message to the A2A service and monitoring the response.
        """
        # 1. Yield the initial event
        yield Event(author=self.name)

        try:
            # 2. Extract the user's message from the context
            user_message = None

            # Search for the user's message in the session events
            if ctx.session and hasattr(ctx.session, "events") and ctx.session.events:
                for event in reversed(ctx.session.events):
                    if event.author == "user" and event.content and event.content.parts:
                        user_message = event.content.parts[0].text
                        logger.info("Message found in session events")
                        break

            # Check in the session state if the message was not found in the events
            if not user_message and ctx.session and ctx.session.state:
                if "user_message" in ctx.session.state:
                    user_message = ctx.session.state["user_message"]
                elif "message" in ctx.session.state:
                    user_message = ctx.session.state["message"]

            if not user_message:
                yield Event(
                    author=self.name,
                    content=Content(
                        role="agent",
                        parts=[
                            Part(text="Error: No message found to send to A2A agent")
                        ],
                    ),
                )
                yield Event(author=self.name)  # Final event
                return

            # 3. Create and send the task to the A2A agent
            logger.info(f"Sending task to A2A agent: {user_message[:100]}...")

            # Use the session ID as a stable identifier
            session_id = (
                str(ctx.session.id)
                if ctx.session and hasattr(ctx.session, "id")
                else str(uuid4())
            )
            task_id = str(uuid4())
            request_id = str(uuid4())

            try:
                # Format message according to A2A protocol
                formatted_message = Message(
                    role="user",
                    parts=[TextPart(type="text", text=user_message)],
                )

                # Prepare standard params for A2A
                task_params = {
                    "id": task_id,
                    "sessionId": session_id,
                    "message": formatted_message,
                    "acceptedOutputModes": ["text"],
                }

                # Emit processing message
                yield Event(
                    author=self.name,
                    content=Content(
                        role="agent", parts=[Part(text="Processing your request...")]
                    ),
                )

                if self.streaming:
                    # Use streaming mode
                    request = SendTaskStreamingRequest(
                        id=request_id, params=task_params
                    )

                    # Handle streaming response
                    accumulated_response = ""

                    try:
                        async with httpx.AsyncClient(timeout=None) as client:
                            async with client.stream(
                                "POST",
                                self.base_url,
                                json=request.model_dump(),
                                headers=self.headers,
                            ) as response:
                                response.raise_for_status()

                                # Process SSE events
                                async for line in response.aiter_lines():
                                    if not line or line.strip() == "":
                                        continue

                                    if line.startswith("data:"):
                                        data = line[5:].strip()
                                        try:
                                            event_data = json.loads(data)
                                            logger.debug(f"SSE event: {event_data}")

                                            # Process artifacts
                                            if (
                                                "result" in event_data
                                                and "artifact" in event_data["result"]
                                            ):
                                                artifact = event_data["result"][
                                                    "artifact"
                                                ]
                                                if artifact and "parts" in artifact:
                                                    for part in artifact["parts"]:
                                                        if (
                                                            "text" in part
                                                            and part["text"]
                                                        ):
                                                            accumulated_response += (
                                                                part["text"]
                                                            )

                                                            # Emit incremental update
                                                            yield Event(
                                                                author=self.name,
                                                                content=Content(
                                                                    role="agent",
                                                                    parts=[
                                                                        Part(
                                                                            text=accumulated_response
                                                                        )
                                                                    ],
                                                                ),
                                                            )

                                            # Check if task is complete
                                            if (
                                                "result" in event_data
                                                and "status" in event_data["result"]
                                                and "final" in event_data["result"]
                                                and event_data["result"]["final"]
                                            ):
                                                logger.info(
                                                    "Task completed in streaming mode"
                                                )
                                                break

                                        except json.JSONDecodeError as e:
                                            logger.error(
                                                f"Error parsing SSE event: {e}"
                                            )

                    except Exception as e:
                        logger.error(f"Error in streaming mode: {e}")
                        yield Event(
                            author=self.name,
                            content=Content(
                                role="agent",
                                parts=[Part(text=f"Error in streaming mode: {str(e)}")],
                            ),
                        )

                    # If we have a response, we're done
                    if accumulated_response:
                        yield Event(author=self.name)  # Final event
                        return

                else:
                    # Use non-streaming mode
                    request = SendTaskRequest(id=request_id, params=task_params)

                    # Make the request
                    response_data = await self._send_jsonrpc_request(request)

                    # Process the response
                    if "result" in response_data and response_data["result"]:
                        task_result = response_data["result"]

                        # Extract message from response
                        if (
                            "status" in task_result
                            and "message" in task_result["status"]
                            and "parts" in task_result["status"]["message"]
                        ):

                            parts = task_result["status"]["message"]["parts"]
                            for part in parts:
                                if "text" in part and part["text"]:
                                    yield Event(
                                        author=self.name,
                                        content=Content(
                                            role="agent",
                                            parts=[Part(text=part["text"])],
                                        ),
                                    )
                                    yield Event(author=self.name)  # Final event
                                    return

                # If we reach here, we need to poll for results
                start_time = time.time()

                while time.time() - start_time < self.timeout:
                    try:
                        # Check current status
                        status_request = GetTaskRequest(
                            id=request_id, params={"id": task_id, "historyLength": 10}
                        )

                        task_status = await self._send_jsonrpc_request(status_request)

                        if "result" not in task_status or not task_status["result"]:
                            await asyncio.sleep(self.poll_interval)
                            continue

                        current_state = None
                        if (
                            "status" in task_status["result"]
                            and task_status["result"]["status"]
                        ):
                            if "state" in task_status["result"]["status"]:
                                current_state = task_status["result"]["status"]["state"]

                        logger.info(f"Task status {task_id}: {current_state}")

                        # Check if the task was completed
                        if current_state in [
                            TaskState.COMPLETED,
                            TaskState.FAILED,
                            TaskState.CANCELED,
                        ]:
                            if current_state == TaskState.COMPLETED:
                                # Extract the response
                                if (
                                    "status" in task_status["result"]
                                    and "message" in task_status["result"]["status"]
                                    and "parts"
                                    in task_status["result"]["status"]["message"]
                                ):

                                    # Convert A2A parts to ADK
                                    response_parts = []
                                    for part in task_status["result"]["status"][
                                        "message"
                                    ]["parts"]:
                                        if "text" in part and part["text"]:
                                            response_parts.append(
                                                Part(text=part["text"])
                                            )
                                        elif "data" in part:
                                            try:
                                                json_text = json.dumps(
                                                    part["data"],
                                                    ensure_ascii=False,
                                                    indent=2,
                                                )
                                                response_parts.append(
                                                    Part(
                                                        text=f"```json\n{json_text}\n```"
                                                    )
                                                )
                                            except Exception:
                                                response_parts.append(
                                                    Part(text="[Unserializable data]")
                                                )

                                    if response_parts:
                                        yield Event(
                                            author=self.name,
                                            content=Content(
                                                role="agent", parts=response_parts
                                            ),
                                        )
                                    else:
                                        yield Event(
                                            author=self.name,
                                            content=Content(
                                                role="agent",
                                                parts=[
                                                    Part(
                                                        text="Empty response from agent."
                                                    )
                                                ],
                                            ),
                                        )
                                else:
                                    yield Event(
                                        author=self.name,
                                        content=Content(
                                            role="agent",
                                            parts=[
                                                Part(
                                                    text="Task completed, but no response message."
                                                )
                                            ],
                                        ),
                                    )
                            elif current_state == TaskState.FAILED:
                                yield Event(
                                    author=self.name,
                                    content=Content(
                                        role="agent",
                                        parts=[
                                            Part(
                                                text="The task failed during processing."
                                            )
                                        ],
                                    ),
                                )
                            else:  # CANCELED
                                yield Event(
                                    author=self.name,
                                    content=Content(
                                        role="agent",
                                        parts=[Part(text="The task was canceled.")],
                                    ),
                                )

                            # Store in the session state for future reference
                            if ctx.session:
                                try:
                                    ctx.session.state["a2a_task_result"] = task_status[
                                        "result"
                                    ]
                                except Exception:
                                    pass

                            break  # Exit the loop of checking

                    except Exception as e:
                        logger.error(f"Error checking task: {str(e)}")

                        # If the timeout was exceeded, inform the user
                        if time.time() - start_time > self.max_wait_time:
                            yield Event(
                                author=self.name,
                                content=Content(
                                    role="agent",
                                    parts=[Part(text=f"Error checking task: {str(e)}")],
                                ),
                            )
                            break

                    # Wait before the next check
                    await asyncio.sleep(self.poll_interval)

                # If the timeout was exceeded
                if time.time() - start_time >= self.timeout:
                    yield Event(
                        author=self.name,
                        content=Content(
                            role="agent",
                            parts=[
                                Part(
                                    text="The operation exceeded the timeout. Please try again later."
                                )
                            ],
                        ),
                    )

            except Exception as e:
                logger.error(f"Error sending task: {str(e)}")
                yield Event(
                    author=self.name,
                    content=Content(
                        role="agent",
                        parts=[
                            Part(text=f"Error interacting with A2A agent: {str(e)}")
                        ],
                    ),
                )

        except Exception as e:
            # Handle any uncaught error
            logger.error(f"Error executing A2A agent: {str(e)}")
            yield Event(
                author=self.name,
                content=Content(
                    role="agent",
                    parts=[Part(text=f"Error interacting with A2A agent: {str(e)}")],
                ),
            )

        finally:
            # Ensure that the final event is always generated
            yield Event(author=self.name)
