import os
from typing import Any, Dict
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents import SequentialAgent, ParallelAgent, LoopAgent
from google.adk.runners import Runner
from google.genai.types import Content, Part
from google.adk.sessions import DatabaseSessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from src.utils.logger import setup_logger
from src.core.exceptions import AgentNotFoundError, InternalServerError
from src.services.agent_service import get_agent
from src.services.agent_builder import AgentBuilder
from sqlalchemy.orm import Session
from contextlib import AsyncExitStack

logger = setup_logger(__name__)


async def run_agent(
    agent_id: str,
    contact_id: str,
    message: str,
    session_service: DatabaseSessionService,
    artifacts_service: InMemoryArtifactService,
    memory_service: InMemoryMemoryService,
    db: Session,
):
    try:
        logger.info(
            f"Iniciando execução do agente {agent_id} para contato {contact_id}"
        )
        logger.info(f"Mensagem recebida: {message}")

        get_root_agent = get_agent(db, agent_id)
        logger.info(
            f"Agente root encontrado: {get_root_agent.name} (tipo: {get_root_agent.type})"
        )

        if get_root_agent is None:
            raise AgentNotFoundError(f"Agente com ID {agent_id} não encontrado")

        # Usando o AgentBuilder para criar o agente
        agent_builder = AgentBuilder(db, memory_service)
        root_agent, exit_stack = await agent_builder.build_agent(get_root_agent)

        logger.info("Configurando Runner")
        agent_runner = Runner(
            agent=root_agent,
            app_name=get_root_agent.name,
            session_service=session_service,
            artifact_service=artifacts_service,
        )
        session_id = contact_id + "_" + agent_id

        logger.info(f"Buscando sessão para contato {contact_id}")
        session = session_service.get_session(
            app_name=root_agent.name,
            user_id=contact_id,
            session_id=session_id,
        )

        if session is None:
            logger.info(f"Criando nova sessão para contato {contact_id}")
            session = session_service.create_session(
                app_name=root_agent.name,
                user_id=contact_id,
                session_id=session_id,
            )

        content = Content(role="user", parts=[Part(text=message)])
        logger.info("Iniciando execução do agente")

        final_response_text = None
        try:
            for event in agent_runner.run(
                user_id=contact_id,
                session_id=session_id,
                new_message=content,
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    final_response_text = event.content.parts[0].text
                    logger.info(f"Resposta final recebida: {final_response_text}")
        finally:
            # Garante que o exit_stack seja fechado corretamente
            if exit_stack:
                await exit_stack.aclose()

        logger.info("Execução do agente concluída com sucesso")
        return final_response_text
    except AgentNotFoundError as e:
        logger.error(f"Erro ao processar requisição: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Erro interno ao processar requisição: {str(e)}", exc_info=True)
        raise InternalServerError(str(e))
