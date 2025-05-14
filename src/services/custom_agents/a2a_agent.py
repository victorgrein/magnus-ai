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

from typing import AsyncGenerator, List

from src.schemas.a2a_types import (
    SendTaskRequest,
    Message,
    TextPart,
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
    timeout: int

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
        # Initialize base class
        super().__init__(
            name=name,
            agent_card_url=agent_card_url,
            timeout=timeout,
            sub_agents=sub_agents,
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
                    url, json=request.model_dump(), timeout=self.timeout
                )

                print(f"Task response: {task_result.json()}")
                print(f"Task sent successfully, ID: {task_id}")

                agent_response_parts = task_result.json()["result"]["status"][
                    "message"
                ]["parts"]

                parts = [Part(text=part["text"]) for part in agent_response_parts]

                yield Event(
                    author=self.name,
                    content=Content(role="agent", parts=parts),
                )

                # Run sub-agents
                for sub_agent in self.sub_agents:
                    async for event in sub_agent.run_async(ctx):
                        yield event

            except Exception as e:
                error_msg = f"Error sending request: {str(e)}"
                print(error_msg)
                print(f"Error type: {type(e).__name__}")
                print(f"Error details: {str(e)}")

                yield Event(
                    author=self.name,
                    content=Content(role="agent", parts=[Part(text=error_msg)]),
                )
                return

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
