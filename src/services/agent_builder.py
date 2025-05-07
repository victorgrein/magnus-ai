from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents import SequentialAgent, ParallelAgent, LoopAgent, BaseAgent
from google.adk.models.lite_llm import LiteLlm
from src.utils.logger import setup_logger
from src.core.exceptions import AgentNotFoundError
from src.services.agent_service import get_agent
from src.services.custom_tools import CustomToolBuilder
from src.services.mcp_service import MCPService
from src.services.a2a_agent import A2ACustomAgent
from src.services.workflow_agent import WorkflowAgent
from src.services.apikey_service import get_decrypted_api_key
from sqlalchemy.orm import Session
from contextlib import AsyncExitStack
from google.adk.tools import load_memory

from datetime import datetime
import uuid

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
        if agent.config.get("mcp_servers") or agent.config.get("custom_mcp_servers"):
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
        if agent.config.get("load_memory"):
            all_tools.append(load_memory)
            formatted_prompt = (
                formatted_prompt
                + "\n\n<memory_instructions>ALWAYS use the load_memory tool to retrieve knowledge for your context</memory_instructions>\n\n"
            )

        # Get API key from api_key_id
        api_key = None

        # Get API key from api_key_id
        if hasattr(agent, "api_key_id") and agent.api_key_id:
            decrypted_key = get_decrypted_api_key(self.db, agent.api_key_id)
            if decrypted_key:
                logger.info(f"Using stored API key for agent {agent.name}")
                api_key = decrypted_key
            else:
                logger.error(f"Stored API key not found for agent {agent.name}")
                raise ValueError(
                    f"API key with ID {agent.api_key_id} not found or inactive"
                )
        else:
            # Check if there is an API key in the config (temporary field)
            config_api_key = agent.config.get("api_key") if agent.config else None
            if config_api_key:
                logger.info(f"Using config API key for agent {agent.name}")
                # Check if it is a UUID of a stored key
                try:
                    key_id = uuid.UUID(config_api_key)
                    decrypted_key = get_decrypted_api_key(self.db, key_id)
                    if decrypted_key:
                        logger.info("Config API key is a valid reference")
                        api_key = decrypted_key
                    else:
                        # Use the key directly
                        api_key = config_api_key
                except (ValueError, TypeError):
                    # It is not a UUID, use directly
                    api_key = config_api_key
            else:
                logger.error(f"No API key configured for agent {agent.name}")
                raise ValueError(
                    f"Agent {agent.name} does not have a configured API key"
                )

        return (
            LlmAgent(
                name=agent.name,
                model=LiteLlm(model=agent.model, api_key=api_key),
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
            sub_agent_id_str = str(sub_agent_id)

            agent = get_agent(self.db, sub_agent_id_str)

            if agent is None:
                logger.error(f"Sub-agent not found: {sub_agent_id_str}")
                raise AgentNotFoundError(f"Agent with ID {sub_agent_id_str} not found")

            logger.info(f"Sub-agent found: {agent.name} (type: {agent.type})")

            if agent.type == "llm":
                sub_agent, exit_stack = await self._create_llm_agent(agent)
            elif agent.type == "a2a":
                sub_agent, exit_stack = await self.build_a2a_agent(agent)
            elif agent.type == "workflow":
                sub_agent, exit_stack = await self.build_workflow_agent(agent)
            elif agent.type == "sequential":
                sub_agent, exit_stack = await self.build_composite_agent(agent)
            elif agent.type == "parallel":
                sub_agent, exit_stack = await self.build_composite_agent(agent)
            elif agent.type == "loop":
                sub_agent, exit_stack = await self.build_composite_agent(agent)
            else:
                raise ValueError(f"Invalid agent type: {agent.type}")

            sub_agents.append((sub_agent, exit_stack))
            logger.info(f"Sub-agent added: {agent.name}")

        logger.info(f"Sub-agents created: {len(sub_agents)}")
        logger.info(f"Sub-agents: {str(sub_agents)}")

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
            sub_agents = []
            if root_agent.config.get("sub_agents"):
                sub_agents_with_stacks = await self._get_sub_agents(
                    root_agent.config.get("sub_agents")
                )
                sub_agents = [agent for agent, _ in sub_agents_with_stacks]

            config = root_agent.config or {}
            timeout = config.get("timeout", 300)

            a2a_agent = A2ACustomAgent(
                name=root_agent.name,
                agent_card_url=root_agent.agent_card_url,
                timeout=timeout,
                description=root_agent.description
                or f"A2A Agent for {root_agent.name}",
                sub_agents=sub_agents,
            )

            logger.info(
                f"A2A agent created successfully: {root_agent.name} ({root_agent.agent_card_url})"
            )

            return a2a_agent, None

        except Exception as e:
            logger.error(f"Error building A2A agent: {str(e)}")
            raise ValueError(f"Error building A2A agent: {str(e)}")

    async def build_workflow_agent(
        self, root_agent
    ) -> Tuple[WorkflowAgent, Optional[AsyncExitStack]]:
        """Build a workflow agent with its sub-agents."""
        logger.info(f"Creating Workflow agent from {root_agent.name}")

        agent_config = root_agent.config or {}

        if not agent_config.get("workflow"):
            raise ValueError("workflow is required for workflow agents")

        try:
            sub_agents = []
            if root_agent.config.get("sub_agents"):
                sub_agents_with_stacks = await self._get_sub_agents(
                    root_agent.config.get("sub_agents")
                )
                sub_agents = [agent for agent, _ in sub_agents_with_stacks]

            config = root_agent.config or {}
            timeout = config.get("timeout", 300)

            workflow_agent = WorkflowAgent(
                name=root_agent.name,
                flow_json=agent_config.get("workflow"),
                timeout=timeout,
                description=root_agent.description
                or f"Workflow Agent for {root_agent.name}",
                sub_agents=sub_agents,
                db=self.db,
            )

            logger.info(f"Workflow agent created successfully: {root_agent.name}")

            return workflow_agent, None

        except Exception as e:
            logger.error(f"Error building Workflow agent: {str(e)}")
            raise ValueError(f"Error building Workflow agent: {str(e)}")

    async def build_composite_agent(
        self, root_agent
    ) -> Tuple[SequentialAgent | ParallelAgent | LoopAgent, Optional[AsyncExitStack]]:
        """Build a composite agent (Sequential, Parallel or Loop) with its sub-agents."""
        logger.info(
            f"Processing sub-agents for agent {root_agent.type} (ID: {root_agent.id}, Name: {root_agent.name})"
        )

        if not root_agent.config.get("sub_agents"):
            logger.error(
                f"Sub_agents configuration not found or empty for agent {root_agent.name}"
            )
            raise ValueError(f"Missing sub_agents configuration for {root_agent.name}")

        logger.info(
            f"Sub-agents IDs to be processed: {root_agent.config.get('sub_agents', [])}"
        )

        sub_agents_with_stacks = await self._get_sub_agents(
            root_agent.config.get("sub_agents", [])
        )

        logger.info(
            f"Sub-agents processed: {len(sub_agents_with_stacks)} of {len(root_agent.config.get('sub_agents', []))}"
        )

        sub_agents = [agent for agent, _ in sub_agents_with_stacks]
        logger.info(f"Extracted sub-agents: {[agent.name for agent in sub_agents]}")

        if root_agent.type == "sequential":
            logger.info(f"Creating SequentialAgent with {len(sub_agents)} sub-agents")
            return (
                SequentialAgent(
                    name=root_agent.name,
                    sub_agents=sub_agents,
                    description=root_agent.config.get("description", ""),
                ),
                None,
            )
        elif root_agent.type == "parallel":
            logger.info(f"Creating ParallelAgent with {len(sub_agents)} sub-agents")
            return (
                ParallelAgent(
                    name=root_agent.name,
                    sub_agents=sub_agents,
                    description=root_agent.config.get("description", ""),
                ),
                None,
            )
        elif root_agent.type == "loop":
            logger.info(f"Creating LoopAgent with {len(sub_agents)} sub-agents")
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
        LlmAgent
        | SequentialAgent
        | ParallelAgent
        | LoopAgent
        | A2ACustomAgent
        | WorkflowAgent,
        Optional[AsyncExitStack],
    ]:
        """Build the appropriate agent based on the type of the root agent."""
        if root_agent.type == "llm":
            return await self.build_llm_agent(root_agent)
        elif root_agent.type == "a2a":
            return await self.build_a2a_agent(root_agent)
        elif root_agent.type == "workflow":
            return await self.build_workflow_agent(root_agent)
        else:
            return await self.build_composite_agent(root_agent)
