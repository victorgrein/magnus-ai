from typing import List, Optional
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents import SequentialAgent, ParallelAgent, LoopAgent
from google.adk.models.lite_llm import LiteLlm
from src.utils.logger import setup_logger
from src.core.exceptions import AgentNotFoundError
from src.services.agent_service import get_agent
from src.services.custom_tools import CustomToolBuilder
from sqlalchemy.orm import Session

logger = setup_logger(__name__)

class AgentBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.custom_tool_builder = CustomToolBuilder()

    def _create_llm_agent(self, agent) -> LlmAgent:
        """Cria um agente LLM a partir dos dados do agente."""
        # Obtém ferramentas personalizadas da configuração
        custom_tools = []
        if agent.config.get("tools"):
            custom_tools = self.custom_tool_builder.build_tools(agent.config["tools"])

        return LlmAgent(
            name=agent.name,
            model=LiteLlm(model=agent.model, api_key=agent.api_key),
            instruction=agent.instruction,
            description=agent.config.get("description", ""),
            tools=custom_tools,
        )

    def _get_sub_agents(self, sub_agent_ids: List[str]) -> List[LlmAgent]:
        """Obtém e cria os sub-agentes LLM."""
        sub_agents = []
        for sub_agent_id in sub_agent_ids:
            agent = get_agent(self.db, sub_agent_id)
            
            if agent is None:
                raise AgentNotFoundError(f"Agente com ID {sub_agent_id} não encontrado")
            
            if agent.type != "llm":
                raise ValueError(f"Agente {agent.name} (ID: {agent.id}) não é um agente LLM")
            
            sub_agents.append(self._create_llm_agent(agent))
        
        return sub_agents

    def build_llm_agent(self, root_agent) -> LlmAgent:
        """Constrói um agente LLM com seus sub-agentes."""
        logger.info("Criando agente LLM")
        
        sub_agents = []
        if root_agent.config.get("sub_agents"):
            sub_agents = self._get_sub_agents(root_agent.config.get("sub_agents"))
        
        root_llm_agent = self._create_llm_agent(root_agent)
        if sub_agents:
            root_llm_agent.sub_agents = sub_agents
        
        return root_llm_agent

    def build_composite_agent(self, root_agent) -> SequentialAgent | ParallelAgent | LoopAgent:
        """Constrói um agente composto (Sequential, Parallel ou Loop) com seus sub-agentes."""
        logger.info(f"Processando sub-agentes para agente {root_agent.type}")
        
        sub_agents = self._get_sub_agents(root_agent.config.get("sub_agents", []))
        
        if root_agent.type == "sequential":
            logger.info("Criando SequentialAgent")
            return SequentialAgent(
                name=root_agent.name,
                sub_agents=sub_agents,
                description=root_agent.config.get("description", ""),
            )
        elif root_agent.type == "parallel":
            logger.info("Criando ParallelAgent")
            return ParallelAgent(
                name=root_agent.name,
                sub_agents=sub_agents,
                description=root_agent.config.get("description", ""),
            )
        elif root_agent.type == "loop":
            logger.info("Criando LoopAgent")
            return LoopAgent(
                name=root_agent.name,
                sub_agents=sub_agents,
                description=root_agent.config.get("description", ""),
                max_iterations=root_agent.config.get("max_iterations", 5),
            )
        else:
            raise ValueError(f"Tipo de agente inválido: {root_agent.type}")

    def build_agent(self, root_agent) -> LlmAgent | SequentialAgent | ParallelAgent | LoopAgent:
        """Constrói o agente apropriado baseado no tipo do agente root."""
        if root_agent.type == "llm":
            return self.build_llm_agent(root_agent)
        else:
            return self.build_composite_agent(root_agent) 