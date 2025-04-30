from typing import List, Optional, Tuple
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents import SequentialAgent, ParallelAgent, LoopAgent, BaseAgent
from google.adk.models.lite_llm import LiteLlm
from src.utils.logger import setup_logger
from src.core.exceptions import AgentNotFoundError
from src.services.agent_service import get_agent
from src.services.custom_tools import CustomToolBuilder
from src.services.mcp_service import MCPService
from src.services.a2a_agent import A2ACustomAgent
from sqlalchemy.orm import Session
from contextlib import AsyncExitStack
from google.adk.tools import load_memory

from datetime import datetime

logger = setup_logger(__name__)


class AgentBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.custom_tool_builder = CustomToolBuilder()
        self.mcp_service = MCPService()

    async def _create_llm_agent(
        self, agent
    ) -> Tuple[LlmAgent, Optional[AsyncExitStack]]:
        """Create an LLM agent from the agent data."""
        # Get custom tools from the configuration
        custom_tools = []
        if agent.config.get("tools"):
            custom_tools = self.custom_tool_builder.build_tools(agent.config["tools"])

        # Get MCP tools from the configuration
        mcp_tools = []
        mcp_exit_stack = None
        if agent.config.get("mcp_servers"):
            mcp_tools, mcp_exit_stack = await self.mcp_service.build_tools(
                agent.config, self.db
            )

        # Combine all tools
        all_tools = custom_tools + mcp_tools

        now = datetime.now()
        current_datetime = now.strftime("%d/%m/%Y %H:%M")
        current_day_of_week = now.strftime("%A")
        current_date_iso = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")

        # Substitute variables in the prompt
        formatted_prompt = agent.instruction.format(
            current_datetime=current_datetime,
            current_day_of_week=current_day_of_week,
            current_date_iso=current_date_iso,
            current_time=current_time,
        )

        # Check if load_memory is enabled
        # before_model_callback_func = None
        if agent.config.get("load_memory"):
            all_tools.append(load_memory)
            formatted_prompt = (
                formatted_prompt
                + "\n\n<memory_instructions>ALWAYS use the load_memory tool to retrieve knowledge for your context</memory_instructions>\n\n"
            )

        return (
            LlmAgent(
                name=agent.name,
                model=LiteLlm(model=agent.model, api_key=agent.api_key),
                instruction=formatted_prompt,
                description=agent.description,
                tools=all_tools,
            ),
            mcp_exit_stack,
        )

    async def _get_sub_agents(
        self, sub_agent_ids: List[str]
    ) -> List[Tuple[LlmAgent, Optional[AsyncExitStack]]]:
        """Get and create LLM sub-agents."""
        sub_agents = []
        for sub_agent_id in sub_agent_ids:
            agent = get_agent(self.db, sub_agent_id)

            if agent is None:
                raise AgentNotFoundError(f"Agent with ID {sub_agent_id} not found")

            if agent.type == "llm":
                sub_agent, exit_stack = await self._create_llm_agent(agent)
            elif agent.type == "a2a":
                sub_agent, exit_stack = await self.build_a2a_agent(agent)
            elif agent.type == "sequential":
                sub_agent, exit_stack = await self.build_composite_agent(agent)
            elif agent.type == "parallel":
                sub_agent, exit_stack = await self.build_composite_agent(agent)
            elif agent.type == "loop":
                sub_agent, exit_stack = await self.build_composite_agent(agent)
            else:
                raise ValueError(f"Invalid agent type: {agent.type}")

            sub_agents.append((sub_agent, exit_stack))

        return sub_agents

    async def build_llm_agent(
        self, root_agent
    ) -> Tuple[LlmAgent, Optional[AsyncExitStack]]:
        """Build an LLM agent with its sub-agents."""
        logger.info("Creating LLM agent")

        sub_agents = []
        if root_agent.config.get("sub_agents"):
            sub_agents_with_stacks = await self._get_sub_agents(
                root_agent.config.get("sub_agents")
            )
            sub_agents = [agent for agent, _ in sub_agents_with_stacks]

        root_llm_agent, exit_stack = await self._create_llm_agent(root_agent)
        if sub_agents:
            root_llm_agent.sub_agents = sub_agents

        return root_llm_agent, exit_stack

    async def build_a2a_agent(
        self, root_agent
    ) -> Tuple[BaseAgent, Optional[AsyncExitStack]]:
        """Build an A2A agent with its sub-agents."""
        logger.info(f"Creating A2A agent from {root_agent.agent_card_url}")

        if not root_agent.agent_card_url:
            raise ValueError("agent_card_url is required for a2a agents")

        try:
            config = root_agent.config or {}
            poll_interval = config.get("poll_interval", 1.0)
            max_wait_time = config.get("max_wait_time", 60)
            timeout = config.get("timeout", 300)

            a2a_agent = A2ACustomAgent(
                name=root_agent.name,
                agent_card_url=root_agent.agent_card_url,
                poll_interval=poll_interval,
                max_wait_time=max_wait_time,
                timeout=timeout,
                description=root_agent.description
                or f"A2A Agent for {root_agent.name}",
            )

            logger.info(
                f"A2A agent created successfully: {root_agent.name} ({root_agent.agent_card_url})"
            )

            return a2a_agent, None

        except Exception as e:
            logger.error(f"Error building A2A agent: {str(e)}")
            raise ValueError(f"Error building A2A agent: {str(e)}")

    async def build_composite_agent(
        self, root_agent
    ) -> Tuple[SequentialAgent | ParallelAgent | LoopAgent, Optional[AsyncExitStack]]:
        """Build a composite agent (Sequential, Parallel or Loop) with its sub-agents."""
        logger.info(f"Processing sub-agents for agent {root_agent.type}")

        sub_agents_with_stacks = await self._get_sub_agents(
            root_agent.config.get("sub_agents", [])
        )
        sub_agents = [agent for agent, _ in sub_agents_with_stacks]

        if root_agent.type == "sequential":
            logger.info("Creating SequentialAgent")
            return (
                SequentialAgent(
                    name=root_agent.name,
                    sub_agents=sub_agents,
                    description=root_agent.config.get("description", ""),
                ),
                None,
            )
        elif root_agent.type == "parallel":
            logger.info("Creating ParallelAgent")
            return (
                ParallelAgent(
                    name=root_agent.name,
                    sub_agents=sub_agents,
                    description=root_agent.config.get("description", ""),
                ),
                None,
            )
        elif root_agent.type == "loop":
            logger.info("Creating LoopAgent")
            return (
                LoopAgent(
                    name=root_agent.name,
                    sub_agents=sub_agents,
                    description=root_agent.config.get("description", ""),
                    max_iterations=root_agent.config.get("max_iterations", 5),
                ),
                None,
            )
        else:
            raise ValueError(f"Invalid agent type: {root_agent.type}")

    async def build_agent(self, root_agent) -> Tuple[
        LlmAgent | SequentialAgent | ParallelAgent | LoopAgent | A2ACustomAgent,
        Optional[AsyncExitStack],
    ]:
        """Build the appropriate agent based on the type of the root agent."""
        if root_agent.type == "llm":
            return await self.build_llm_agent(root_agent)
        elif root_agent.type == "a2a":
            return await self.build_a2a_agent(root_agent)
        else:
            return await self.build_composite_agent(root_agent)
