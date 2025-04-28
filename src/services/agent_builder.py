from typing import List, Optional, Tuple
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents import SequentialAgent, ParallelAgent, LoopAgent
from google.adk.models.lite_llm import LiteLlm
from src.utils.logger import setup_logger
from src.core.exceptions import AgentNotFoundError
from src.services.agent_service import get_agent
from src.services.custom_tools import CustomToolBuilder
from src.services.mcp_service import MCPService
from sqlalchemy.orm import Session
from contextlib import AsyncExitStack
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse, LlmRequest
from google.adk.tools import load_memory

from typing import Optional
import logging
import os
import requests
from datetime import datetime
logger = setup_logger(__name__)


def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """
    Callback executed before the model generates a response.
    Always executes a search in the knowledge base before proceeding.
    """
    try:
        agent_name = callback_context.agent_name
        logger.debug(f"🔄 Before model call for agent: {agent_name}")

        # Extract the last user message
        last_user_message = ""
        if llm_request.contents and llm_request.contents[-1].role == "user":
            if llm_request.contents[-1].parts:
                last_user_message = llm_request.contents[-1].parts[0].text
                logger.debug(f"📝 Última mensagem do usuário: {last_user_message}")

        # Extract and format the history of messages
        history = []
        for content in llm_request.contents:
            if content.parts and content.parts[0].text:
                # Replace 'model' with 'assistant' in the role
                role = "assistant" if content.role == "model" else content.role
                history.append(
                    {
                        "role": role,
                        "content": {
                            "type": "text",
                            "text": content.parts[0].text,
                        },
                    }
                )

        # log the history of messages
        logger.debug(f"📝 History of messages: {history}")

        if last_user_message:
            logger.info("🔍 Executing knowledge base search")
            # Execute the knowledge base search synchronously
            search_results = search_knowledge_base_function_sync(
                last_user_message, history
            )

            if search_results:
                logger.info("✅ Resultados encontrados, adicionando ao contexto")

                # Get the original system instruction
                original_instruction = llm_request.config.system_instruction or ""

                # Add the search results and history to the system context
                modified_text = (
                    original_instruction
                    + "\n\n<knowledge_context>\n"
                    + str(search_results)
                    + "\n</knowledge_context>\n\n<history>\n"
                    + str(history)
                    + "\n</history>"
                )
                llm_request.config.system_instruction = modified_text

                logger.debug(
                    f"📝 System instruction updated with search results and history"
                )
            else:
                logger.warning("⚠️ No results found in the search")
        else:
            logger.warning("⚠️ No user message found")

        logger.info("✅ before_model_callback finished")
        return None
    except Exception as e:
        logger.error(f"❌ Error in before_model_callback: {str(e)}", exc_info=True)
        return None


def search_knowledge_base_function_sync(query: str, history=[]):
    """
    Search knowledge base synchronously.

    Args:
        query (str): The search query, with user message and history messages, all in one string

    Returns:
        dict: The search results
    """
    try:
        logger.info("🔍 Starting knowledge base search")
        logger.debug(f"Received query: {query}")

        # url = os.getenv("KNOWLEDGE_API_URL") + "/api/v1/search"
        url = os.getenv("KNOWLEDGE_API_URL") + "/api/v1/knowledge"
        tenant_id = os.getenv("TENANT_ID")
        url = url + "?tenant_id=" + tenant_id
        logger.debug(f"API URL: {url}")
        logger.debug(f"Tenant ID: {tenant_id}")

        headers = {
            "x-api-key": f"{os.getenv('KNOWLEDGE_API_KEY')}",
            "Content-Type": "application/json",
        }
        logger.debug(f"Headers configured: {headers}")

        payload = {
            "gemini_api_key": os.getenv("GOOGLE_API_KEY"),
            "gemini_model": "gemini-2.0-flash-lite-001",
            "gemini_temperature": 0.7,
            "query": query,
            "tenant_id": tenant_id,
            "history": history,
        }

        logger.debug(f"Request payload: {payload}")

        # Using requests to make a synchronous request with timeout
        logger.info("🔄 Making synchronous request to the knowledge API")
        # response = requests.post(url, headers=headers, json=payload)
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            logger.info("✅ Search executed successfully")
            result = response.json()
            logger.debug(f"Search result: {result}")
            return result
        else:
            logger.error(
                f"❌ Error performing search. Status code: {response.status_code}"
            )
            return None
    except requests.exceptions.Timeout:
        logger.error("❌ Timeout performing search")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error in request: {str(e)}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"❌ Error performing search: {str(e)}", exc_info=True)
        return None


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
            mcp_tools, mcp_exit_stack = await self.mcp_service.build_tools(agent.config, self.db)

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
        if agent.config.get("load_memory") == True:
            all_tools.append(load_memory)
            # before_model_callback_func = before_model_callback
            formatted_prompt = formatted_prompt + "\n\n<memory_instructions>ALWAYS use the load_memory tool to retrieve knowledge for your context</memory_instructions>\n\n"

        return (
            LlmAgent(
                name=agent.name,
                model=LiteLlm(model=agent.model, api_key=agent.api_key),
                instruction=formatted_prompt,
                description=agent.description,
                tools=all_tools,
                # before_model_callback=before_model_callback_func,
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

            if agent.type != "llm":
                raise ValueError(
                    f"Agent {agent.name} (ID: {agent.id}) is not an LLM agent"
                )

            sub_agent, exit_stack = await self._create_llm_agent(agent)
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

    async def build_agent(
        self, root_agent
    ) -> Tuple[
        LlmAgent | SequentialAgent | ParallelAgent | LoopAgent, Optional[AsyncExitStack]
    ]:
        """Build the appropriate agent based on the type of the root agent."""
        if root_agent.type == "llm":
            return await self.build_llm_agent(root_agent)
        else:
            return await self.build_composite_agent(root_agent)
