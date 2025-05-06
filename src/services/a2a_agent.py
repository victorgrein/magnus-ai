from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai.types import Content, Part
from typing import AsyncGenerator
import json
import asyncio
import time

from src.schemas.a2a_types import (
    GetTaskRequest,
    SendTaskRequest,
    Message,
    TextPart,
    TaskState,
)

import httpx

from uuid import uuid4


class A2ACustomAgent(BaseAgent):
    """
    Custom agent that implements the A2A protocol directly.

    This agent implements the interaction with an external A2A service.
    """

    # Field declarations for Pydantic
    agent_card_url: str
    poll_interval: float
    max_wait_time: int
    timeout: int

    def __init__(
        self,
        name: str,
        agent_card_url: str,
        poll_interval: float = 1.0,
        max_wait_time: int = 60,
        timeout: int = 300,
        **kwargs,
    ):
        """
        Initialize the A2A agent.

        Args:
            name: Agent name
            agent_card_url: A2A agent card URL
            poll_interval: Status check interval (seconds)
            max_wait_time: Maximum wait time for a task (seconds)
            timeout: Maximum execution time (seconds)
        """
        # Initialize base class
        super().__init__(
            name=name,
            agent_card_url=agent_card_url,
            poll_interval=poll_interval,
            max_wait_time=max_wait_time,
            timeout=timeout,
            **kwargs,
        )

        print(f"A2A agent initialized for URL: {agent_card_url}")

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
            # Prepare the base URL for the A2A
            url = self.agent_card_url

            # Ensure that there is no /.well-known/agent.json in the url
            if "/.well-known/agent.json" in url:
                url = url.split("/.well-known/agent.json")[0]

            # 2. Extract the user's message from the context
            user_message = None

            # Search for the user's message in the session events
            if ctx.session and hasattr(ctx.session, "events") and ctx.session.events:
                for event in reversed(ctx.session.events):
                    if event.author == "user" and event.content and event.content.parts:
                        user_message = event.content.parts[0].text
                        print("Message found in session events")
                        break

            # Check in the session state if the message was not found in the events
            if not user_message and ctx.session and ctx.session.state:
                if "user_message" in ctx.session.state:
                    user_message = ctx.session.state["user_message"]
                elif "message" in ctx.session.state:
                    user_message = ctx.session.state["message"]

            # 3. Create and send the task to the A2A agent
            print(f"Sending task to A2A agent: {user_message[:100]}...")

            # Use the session ID as a stable identifier
            session_id = (
                str(ctx.session.id)
                if ctx.session and hasattr(ctx.session, "id")
                else str(uuid4())
            )
            task_id = str(uuid4())

            try:

                formatted_message: Message = Message(
                    role="user",
                    parts=[TextPart(type="text", text=user_message)],
                )

                request: SendTaskRequest = SendTaskRequest(
                    params={
                        "message": formatted_message,
                        "sessionId": session_id,
                        "id": task_id,
                    }
                )

                print(f"Request send task: {request.model_dump()}")

                # REQUEST POST to url when jsonrpc is 2.0
                task_result = await httpx.AsyncClient().post(
                    url, json=request.model_dump(), timeout=30
                )

                print(f"Task response: {task_result.json()}")
                print(f"Task sent successfully, ID: {task_id}")

                yield Event(
                    author=self.name,
                    content=Content(
                        role="agent", parts=[Part(text="Processing request...")]
                    ),
                )
            except Exception as e:
                error_msg = f"Error sending request: {str(e)}"
                print(error_msg)
                print(f"Error type: {type(e).__name__}")
                print(f"Error details: {str(e)}")

                yield Event(
                    author=self.name,
                    content=Content(role="agent", parts=[Part(text=str(e))]),
                )
                yield Event(author=self.name)  # Final event
                return

            start_time = time.time()

            while time.time() - start_time < self.timeout:
                try:
                    # Check current status
                    request: GetTaskRequest = GetTaskRequest(params={"id": task_id})

                    task_status_response = await httpx.AsyncClient().post(
                        url, json=request.model_dump(), timeout=30
                    )

                    print(f"Response get task: {task_status_response.json()}")

                    task_status = task_status_response.json()

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

                    print(f"Task status {task_id}: {current_state}")

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
                                for part in task_status["result"]["status"]["message"][
                                    "parts"
                                ]:
                                    if "text" in part and part["text"]:
                                        response_parts.append(Part(text=part["text"]))
                                    elif "data" in part:
                                        try:
                                            json_text = json.dumps(
                                                part["data"],
                                                ensure_ascii=False,
                                                indent=2,
                                            )
                                            response_parts.append(
                                                Part(text=f"```json\n{json_text}\n```")
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
                                                Part(text="Empty response from agent.")
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
                                        Part(text="The task failed during processing.")
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
                    print(f"Error checking task: {str(e)}")

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
            # Handle any uncaught error
            print(f"Error executing A2A agent: {str(e)}")
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
