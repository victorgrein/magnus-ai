"""
┌──────────────────────────────────────────────────────────────────────────────┐
│ @author: Davidson Gomes                                                      │
│ @file: a2a_agent.py                                                          │
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

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai.types import Content, Part

from typing import AsyncGenerator, List, Dict, Any, Optional
import json

import httpx
from httpx_sse import connect_sse

from src.schemas.a2a_types import (
    AgentCard,
    Message,
    TextPart,
    TaskSendParams,
    SendTaskRequest,
    SendTaskStreamingRequest,
    TaskState,
)

from uuid import uuid4


class A2ACustomAgent(BaseAgent):
    """
    Custom agent that implements the A2A protocol directly.

    This agent implements the interaction with an external A2A service.
    """

    # Field declarations for Pydantic
    agent_card_url: str
    agent_card: Optional[AgentCard]
    timeout: int
    base_url: str

    def __init__(
        self,
        name: str,
        agent_card_url: str,
        timeout: int = 300,
        sub_agents: List[BaseAgent] = [],
        **kwargs,
    ):
        """
        Initialize the A2A agent.

        Args:
            name: Agent name
            agent_card_url: A2A agent card URL
            timeout: Maximum execution time (seconds)
            sub_agents: List of sub-agents to be executed after the A2A agent
        """
        # Create base_url from agent_card_url
        base_url = agent_card_url
        if "/.well-known/agent.json" in base_url:
            base_url = base_url.split("/.well-known/agent.json")[0]

        print(f"A2A agent initialized for URL: {agent_card_url}")

        # Initialize base class
        super().__init__(
            name=name,
            agent_card_url=agent_card_url,
            base_url=base_url,  # Pass base_url here
            agent_card=None,
            timeout=timeout,
            sub_agents=sub_agents,
            **kwargs,
        )

    async def fetch_agent_card(self) -> AgentCard:
        """Fetch the agent card from the A2A service."""
        if self.agent_card:
            return self.agent_card

        card_url = f"{self.base_url}/.well-known/agent.json"
        print(f"Fetching agent card from: {card_url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(card_url)
            response.raise_for_status()
            try:
                card_data = response.json()
                self.agent_card = AgentCard(**card_data)
                return self.agent_card
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse agent card: {str(e)}")

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Implementation of the A2A protocol according to the Google ADK documentation.

        This method follows the pattern of implementing custom agents,
        sending the user's message to the A2A service and monitoring the response.
        """

        try:
            # 1. First, fetch the agent card if we haven't already
            try:
                agent_card = await self.fetch_agent_card()
                print(f"Agent card fetched: {agent_card.name}")
            except Exception as e:
                error_msg = f"Failed to fetch agent card: {str(e)}"
                print(error_msg)
                yield Event(
                    author=self.name,
                    content=Content(role="agent", parts=[Part(text=error_msg)]),
                )
                return

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

            if not user_message:
                error_msg = "No user message found"
                print(error_msg)
                yield Event(
                    author=self.name,
                    content=Content(role="agent", parts=[Part(text=error_msg)]),
                )
                return

            # 3. Create and format the task to send to the A2A agent
            print(f"Sending task to A2A agent: {user_message[:100]}...")

            # Use the session ID as a stable identifier
            session_id = (
                str(ctx.session.id)
                if ctx.session and hasattr(ctx.session, "id")
                else str(uuid4())
            )
            task_id = str(uuid4())

            # Prepare the message for the A2A agent
            formatted_message = Message(
                role="user",
                parts=[TextPart(text=user_message)],
            )

            # Prepare the task parameters
            task_params = TaskSendParams(
                id=task_id,
                sessionId=session_id,
                message=formatted_message,
                acceptedOutputModes=["text"],
            )

            # 4. Check if the agent supports streaming
            supports_streaming = (
                agent_card.capabilities.streaming if agent_card.capabilities else False
            )

            if supports_streaming:
                print("Agent supports streaming, using streaming API")
                # Process with streaming
                try:
                    request = SendTaskStreamingRequest(
                        method="tasks/sendSubscribe", params=task_params
                    )

                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.post(
                                self.base_url,
                                json=request.model_dump(),
                                headers={"Accept": "text/event-stream"},
                                timeout=self.timeout,
                            )
                            response.raise_for_status()

                            async for line in response.aiter_lines():
                                if line.startswith("data:"):
                                    data = line[5:].strip()
                                    if data:
                                        try:
                                            result = json.loads(data)
                                            print(f"Stream event received: {result}")

                                            # Check if this is a status update with a message
                                            if (
                                                "result" in result
                                                and "status" in result["result"]
                                                and "message"
                                                in result["result"]["status"]
                                                and "parts"
                                                in result["result"]["status"]["message"]
                                            ):
                                                message_parts = result["result"][
                                                    "status"
                                                ]["message"]["parts"]
                                                parts = [
                                                    Part(text=part["text"])
                                                    for part in message_parts
                                                    if part.get("type") == "text"
                                                    and "text" in part
                                                ]

                                                if parts:
                                                    yield Event(
                                                        author=self.name,
                                                        content=Content(
                                                            role="agent", parts=parts
                                                        ),
                                                    )

                                            # Check if this is a final message
                                            if (
                                                "result" in result
                                                and result.get("result", {}).get(
                                                    "final", False
                                                )
                                                and "status" in result["result"]
                                                and result["result"]["status"].get(
                                                    "state"
                                                )
                                                in [
                                                    TaskState.COMPLETED,
                                                    TaskState.CANCELED,
                                                    TaskState.FAILED,
                                                ]
                                            ):
                                                print(
                                                    "Received final message, stream complete"
                                                )
                                                break
                                        except json.JSONDecodeError as e:
                                            print(f"Error parsing SSE data: {str(e)}")
                    except Exception as stream_error:
                        print(
                            f"Error in direct streaming: {str(stream_error)}, falling back to regular API"
                        )
                        fallback_request = SendTaskRequest(
                            method="tasks/send", params=task_params
                        )

                        async with httpx.AsyncClient() as client:
                            response = await client.post(
                                self.base_url,
                                json=fallback_request.model_dump(),
                                timeout=self.timeout,
                            )
                            response.raise_for_status()

                            result = response.json()
                            print(f"Fallback response: {result}")

                            # Extract agent message parts
                            if (
                                "result" in result
                                and "status" in result["result"]
                                and "message" in result["result"]["status"]
                                and "parts" in result["result"]["status"]["message"]
                            ):
                                message_parts = result["result"]["status"]["message"][
                                    "parts"
                                ]
                                parts = [
                                    Part(text=part["text"])
                                    for part in message_parts
                                    if part.get("type") == "text" and "text" in part
                                ]

                                if parts:
                                    yield Event(
                                        author=self.name,
                                        content=Content(role="agent", parts=parts),
                                    )
                            else:
                                yield Event(
                                    author=self.name,
                                    content=Content(
                                        role="agent",
                                        parts=[
                                            Part(
                                                text="Received response without message parts"
                                            )
                                        ],
                                    ),
                                )
                except Exception as e:
                    error_msg = f"Error in streaming: {str(e)}"
                    print(error_msg)
                    yield Event(
                        author=self.name,
                        content=Content(role="agent", parts=[Part(text=error_msg)]),
                    )
            else:
                print("Agent does not support streaming, using regular API")
                # Process with regular request
                try:
                    request = SendTaskRequest(method="tasks/send", params=task_params)

                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            self.base_url,
                            json=request.model_dump(),
                            timeout=self.timeout,
                        )
                        response.raise_for_status()

                        result = response.json()
                        print(f"Task response: {result}")

                        # Extract agent message parts
                        if (
                            "result" in result
                            and "status" in result["result"]
                            and "message" in result["result"]["status"]
                            and "parts" in result["result"]["status"]["message"]
                        ):
                            message_parts = result["result"]["status"]["message"][
                                "parts"
                            ]
                            parts = [
                                Part(text=part["text"])
                                for part in message_parts
                                if part.get("type") == "text" and "text" in part
                            ]

                            if parts:
                                yield Event(
                                    author=self.name,
                                    content=Content(role="agent", parts=parts),
                                )
                        else:
                            yield Event(
                                author=self.name,
                                content=Content(
                                    role="agent",
                                    parts=[
                                        Part(
                                            text="Received response without message parts"
                                        )
                                    ],
                                ),
                            )

                except Exception as e:
                    error_msg = f"Error sending request: {str(e)}"
                    print(error_msg)
                    print(f"Error type: {type(e).__name__}")
                    print(f"Error details: {str(e)}")

                    yield Event(
                        author=self.name,
                        content=Content(role="agent", parts=[Part(text=error_msg)]),
                    )

            # Run sub-agents
            for sub_agent in self.sub_agents:
                async for event in sub_agent.run_async(ctx):
                    yield event

        except Exception as e:
            # Handle any uncaught error
            error_msg = f"Error executing A2A agent: {str(e)}"
            print(error_msg)
            yield Event(
                author=self.name,
                content=Content(
                    role="agent",
                    parts=[Part(text=error_msg)],
                ),
            )
