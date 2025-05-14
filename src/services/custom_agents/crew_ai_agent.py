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

from attr import Factory
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai.types import Content, Part
from src.services.agent_service import get_agent
from src.services.apikey_service import get_decrypted_api_key

from sqlalchemy.orm import Session

from typing import AsyncGenerator, List

from src.schemas.agent_config import CrewAITask

from crewai import Agent, Task, Crew, LLM


class CrewAIAgent(BaseAgent):
    """
    Custom agent that implements the CrewAI protocol directly.

    This agent implements the interaction with an external CrewAI service.
    """

    # Field declarations for Pydantic
    tasks: List[CrewAITask]
    db: Session

    def __init__(
        self,
        name: str,
        tasks: List[CrewAITask],
        db: Session,
        sub_agents: List[BaseAgent] = [],
        **kwargs,
    ):
        """
        Initialize the CrewAI agent.

        Args:
            name: Agent name
            tasks: List of tasks to be executed
            db: Database session
            sub_agents: List of sub-agents to be executed after the CrewAI agent
        """
        # Initialize base class
        super().__init__(
            name=name,
            tasks=tasks,
            db=db,
            sub_agents=sub_agents,
            **kwargs,
        )

    def _generate_llm(self, model: str, api_key: str):
        """
        Generate the LLM for the CrewAI agent.
        """

        return LLM(model=model, api_key=api_key)

    def _agent_builder(self, agent_id: str):
        """
        Build the CrewAI agent.
        """
        agent = get_agent(self.db, agent_id)

        if not agent:
            raise ValueError(f"Agent with id {agent_id} not found")

        api_key = None

        decrypted_key = get_decrypted_api_key(self.db, agent.api_key_id)
        if decrypted_key:
            api_key = decrypted_key
        else:
            raise ValueError(
                f"API key with ID {agent.api_key_id} not found or inactive"
            )

        if not api_key:
            raise ValueError(f"API key for agent {agent.name} not found")

        return Agent(
            role=agent.role,
            goal=agent.goal,
            backstory=agent.instruction,
            llm=self._generate_llm(agent.model, api_key),
            verbose=True,
        )

    def _tasks_and_agents_builder(self):
        """
        Build the CrewAI tasks.
        """
        tasks = []
        agents = []
        for task in self.tasks:
            agent = self._agent_builder(task.agent_id)
            agents.append(agent)
            tasks.append(
                Task(
                    description=task.description,
                    expected_output=task.expected_output,
                    agent=agent,
                )
            )
        return tasks, agents

    def _crew_builder(self):
        """
        Build the CrewAI crew.
        """
        tasks, agents = self._tasks_and_agents_builder()
        return Crew(
            agents=agents,
            tasks=tasks,
            verbose=True,
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Implementation of the CrewAI.

        This method follows the pattern of implementing custom agents,
        sending the user's message to the CrewAI service and monitoring the response.
        """

        try:
            # Extract the user's message from the context
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
                yield Event(
                    author=self.name,
                    content=Content(
                        role="agent",
                        parts=[Part(text="User message not found")],
                    ),
                )
                return

            try:
                # Replace any {content} in the task descriptions with the user's input
                for task in self.tasks:
                    task.description = task.description.replace(
                        "{content}", user_message
                    )

                # Build the Crew
                crew = self._crew_builder()

                # Start the agent status
                yield Event(
                    author=self.name,
                    content=Content(
                        role="agent",
                        parts=[Part(text=f"Starting CrewAI processing...")],
                    ),
                )

                # Prepare inputs (if there are placeholders to replace)
                inputs = {"user_message": user_message}

                # Notify the user that the processing is in progress
                yield Event(
                    author=self.name,
                    content=Content(
                        role="agent",
                        parts=[Part(text=f"Processing your request...")],
                    ),
                )

                # Try first with kickoff() normally
                try:
                    # If it fails, try with kickoff_async
                    result = await crew.kickoff_async(inputs=inputs)
                    print(f"Result of crew.kickoff_async(): {result}")
                except Exception as e:
                    print(f"Error executing crew.kickoff_async(): {str(e)}")
                    print("Trying alternative with crew.kickoff()")
                    result = crew.kickoff(inputs=inputs)
                    print(f"Result of crew.kickoff(): {result}")

                # Create an event for the final result
                final_event = Event(
                    author=self.name,
                    content=Content(role="agent", parts=[Part(text=str(result))]),
                )

                # Transmit the event to the client
                yield final_event

                # Execute sub-agents
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
            print(f"Error executing CrewAI agent: {str(e)}")
            yield Event(
                author=self.name,
                content=Content(
                    role="agent",
                    parts=[Part(text=f"Error interacting with CrewAI agent: {str(e)}")],
                ),
            )
