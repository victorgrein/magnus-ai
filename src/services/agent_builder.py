from typing import List, Optional, Tuple
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents import SequentialAgent, ParallelAgent, LoopAgent
from google.adk.memory import InMemoryMemoryService
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
    Callback executado antes do modelo gerar uma resposta.
    Sempre executa a busca na base de conhecimento antes de prosseguir.
    """
    try:
        agent_name = callback_context.agent_name
        logger.debug(f"🔄 Before model call for agent: {agent_name}")

        # Extrai a última mensagem do usuário
        last_user_message = ""
        if llm_request.contents and llm_request.contents[-1].role == "user":
            if llm_request.contents[-1].parts:
                last_user_message = llm_request.contents[-1].parts[0].text
                logger.debug(f"📝 Última mensagem do usuário: {last_user_message}")

        # Extrai e formata o histórico de mensagens
        history = []
        for content in llm_request.contents:
            if content.parts and content.parts[0].text:
                # Substitui 'model' por 'assistant' no role
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

        # loga o histórico de mensagens
        logger.debug(f"📝 Histórico de mensagens: {history}")

        if last_user_message:
            logger.info("🔍 Executando busca na base de conhecimento")
            # Executa a busca na base de conhecimento de forma síncrona
            search_results = search_knowledge_base_function_sync(
                last_user_message, history
            )

            if search_results:
                logger.info("✅ Resultados encontrados, adicionando ao contexto")

                # Obtém a instrução original do sistema
                original_instruction = llm_request.config.system_instruction or ""

                # Adiciona os resultados da busca e o histórico ao contexto do sistema
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
                    f"📝 Instrução do sistema atualizada com resultados da busca e histórico"
                )
            else:
                logger.warning("⚠️ Nenhum resultado encontrado na busca")
        else:
            logger.warning("⚠️ Nenhuma mensagem do usuário encontrada")

        logger.info("✅ Before_model_callback finalizado")
        return None
    except Exception as e:
        logger.error(f"❌ Erro no before_model_callback: {str(e)}", exc_info=True)
        return None


def search_knowledge_base_function_sync(query: str, history=[]):
    """
    Search knowledge base de forma síncrona.

    Args:
        query (str): The search query, with user message and history messages, all in one string

    Returns:
        dict: The search results
    """
    try:
        logger.info("🔍 Iniciando busca na base de conhecimento")
        logger.debug(f"Query recebida: {query}")

        # url = os.getenv("KNOWLEDGE_API_URL") + "/api/v1/search"
        url = os.getenv("KNOWLEDGE_API_URL") + "/api/v1/knowledge"
        tenant_id = os.getenv("TENANT_ID")
        url = url + "?tenant_id=" + tenant_id
        logger.debug(f"URL da API: {url}")
        logger.debug(f"Tenant ID: {tenant_id}")

        headers = {
            "x-api-key": f"{os.getenv('KNOWLEDGE_API_KEY')}",
            "Content-Type": "application/json",
        }
        logger.debug(f"Headers configurados: {headers}")

        payload = {
            "gemini_api_key": os.getenv("GOOGLE_API_KEY"),
            "gemini_model": "gemini-2.0-flash-lite-001",
            "gemini_temperature": 0.7,
            "query": query,
            "tenant_id": tenant_id,
            "history": history,
        }

        logger.debug(f"Payload da requisição: {payload}")

        # Usando requests para fazer a requisição síncrona com timeout
        logger.info("🔄 Fazendo requisição síncrona para a API de conhecimento")
        # response = requests.post(url, headers=headers, json=payload)
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            logger.info("✅ Busca realizada com sucesso")
            result = response.json()
            logger.debug(f"Resultado da busca: {result}")
            return result
        else:
            logger.error(
                f"❌ Erro ao realizar busca. Status code: {response.status_code}"
            )
            return None
    except requests.exceptions.Timeout:
        logger.error("❌ Timeout ao realizar busca na base de conhecimento")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Erro na requisição: {str(e)}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"❌ Erro ao realizar busca: {str(e)}", exc_info=True)
        return None


class AgentBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.custom_tool_builder = CustomToolBuilder()
        self.mcp_service = MCPService()

    async def _create_llm_agent(
        self, agent
    ) -> Tuple[LlmAgent, Optional[AsyncExitStack]]:
        """Cria um agente LLM a partir dos dados do agente."""
        # Obtém ferramentas personalizadas da configuração
        custom_tools = []
        if agent.config.get("tools"):
            custom_tools = self.custom_tool_builder.build_tools(agent.config["tools"])

        # Obtém ferramentas MCP da configuração
        mcp_tools = []
        mcp_exit_stack = None
        if agent.config.get("mcpServers"):
            mcp_tools, mcp_exit_stack = await self.mcp_service.build_tools(agent.config)

        # Combina todas as ferramentas
        all_tools = custom_tools + mcp_tools
            
        now = datetime.now()
        current_datetime = now.strftime("%d/%m/%Y %H:%M")
        current_day_of_week = now.strftime("%A")
        current_date_iso = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")

        # Substitui as variáveis no prompt
        formatted_prompt = agent.instruction.format(
            current_datetime=current_datetime,
            current_day_of_week=current_day_of_week,
            current_date_iso=current_date_iso,
            current_time=current_time,
        )

        # Verifica se load_memory está habilitado
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
        """Obtém e cria os sub-agentes LLM."""
        sub_agents = []
        for sub_agent_id in sub_agent_ids:
            agent = get_agent(self.db, sub_agent_id)

            if agent is None:
                raise AgentNotFoundError(f"Agente com ID {sub_agent_id} não encontrado")

            if agent.type != "llm":
                raise ValueError(
                    f"Agente {agent.name} (ID: {agent.id}) não é um agente LLM"
                )

            sub_agent, exit_stack = await self._create_llm_agent(agent)
            sub_agents.append((sub_agent, exit_stack))

        return sub_agents

    async def build_llm_agent(
        self, root_agent
    ) -> Tuple[LlmAgent, Optional[AsyncExitStack]]:
        """Constrói um agente LLM com seus sub-agentes."""
        logger.info("Criando agente LLM")

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
        """Constrói um agente composto (Sequential, Parallel ou Loop) com seus sub-agentes."""
        logger.info(f"Processando sub-agentes para agente {root_agent.type}")

        sub_agents_with_stacks = await self._get_sub_agents(
            root_agent.config.get("sub_agents", [])
        )
        sub_agents = [agent for agent, _ in sub_agents_with_stacks]

        if root_agent.type == "sequential":
            logger.info("Criando SequentialAgent")
            return (
                SequentialAgent(
                    name=root_agent.name,
                    sub_agents=sub_agents,
                    description=root_agent.config.get("description", ""),
                ),
                None,
            )
        elif root_agent.type == "parallel":
            logger.info("Criando ParallelAgent")
            return (
                ParallelAgent(
                    name=root_agent.name,
                    sub_agents=sub_agents,
                    description=root_agent.config.get("description", ""),
                ),
                None,
            )
        elif root_agent.type == "loop":
            logger.info("Criando LoopAgent")
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
            raise ValueError(f"Tipo de agente inválido: {root_agent.type}")

    async def build_agent(
        self, root_agent
    ) -> Tuple[
        LlmAgent | SequentialAgent | ParallelAgent | LoopAgent, Optional[AsyncExitStack]
    ]:
        """Constrói o agente apropriado baseado no tipo do agente root."""
        if root_agent.type == "llm":
            return await self.build_llm_agent(root_agent)
        else:
            return await self.build_composite_agent(root_agent)
