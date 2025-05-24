"""
┌──────────────────────────────────────────────────────────────────────────────┐
│ @author: Davidson Gomes                                                      │
│ @file: a2a_sdk_adapter.py                                                    │
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

import logging
import asyncio
from typing import Dict, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

try:
    from a2a.server.agent_execution import AgentExecutor, RequestContext
    from a2a.server.events import EventQueue
    from a2a.server.tasks import TaskStore, InMemoryTaskStore
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.apps import A2AStarletteApplication
    from a2a.types import (
        AgentCard,
        AgentCapabilities,
        AgentSkill,
        AgentProvider,
        Task as SDKTask,
        TaskState as SDKTaskState,
        TaskStatus as SDKTaskStatus,
        Message as SDKMessage,
        TaskStatusUpdateEvent,
        TaskArtifactUpdateEvent,
    )
    from a2a.utils import new_agent_text_message, completed_task

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logging.warning("a2a-sdk not available for adapter")

from src.config.settings import settings
from src.services.agent_service import get_agent
from src.services.mcp_server_service import get_mcp_server
from src.services.a2a_task_manager import A2ATaskManager, A2AService
from src.schemas.a2a_types import (
    SendTaskRequest,
    SendTaskStreamingRequest,
    CancelTaskRequest,
    TaskSendParams,
    TaskState as CustomTaskState,
    TaskStatus as CustomTaskStatus,
)
from src.schemas.a2a_enhanced_types import (
    A2ATypeConverter,
    convert_to_sdk_format,
    convert_from_sdk_format,
)

logger = logging.getLogger(__name__)


class EvoAIAgentExecutor:
    """
    Implementação direta da Message API para o SDK oficial.

    Ao invés de tentar converter para Task API, implementa diretamente
    os métodos esperados pelo SDK: message/send e message/stream
    """

    def __init__(self, db: Session, agent_id: UUID):
        self.db = db
        self.agent_id = agent_id

    async def execute(
        self, context: "RequestContext", event_queue: "EventQueue"
    ) -> None:
        """
        Implementa diretamente a execução de mensagens usando agent_runner.

        Não usa task manager - vai direto para a lógica de execução.
        """
        try:
            logger.info("=" * 80)
            logger.info(f"🚀 EXECUTOR EXECUTE() CHAMADO! Agent: {self.agent_id}")
            logger.info(f"Context: {context}")
            logger.info(f"Message: {getattr(context, 'message', 'NO_MESSAGE')}")
            logger.info("=" * 80)

            # Verifica se há mensagem
            if not hasattr(context, "message") or not context.message:
                logger.error("❌ No message in context")
                await self._emit_error_event(event_queue, "No message provided")
                return

            # Extrai texto da mensagem
            message_text = self._extract_text_from_message(context.message)
            if not message_text:
                logger.error("❌ No text found in message")
                await self._emit_error_event(event_queue, "No text content found")
                return

            logger.info(f"📝 Extracted message: {message_text}")

            # Gera session_id único
            session_id = context.context_id or str(uuid4())
            logger.info(f"📝 Using session_id: {session_id}")

            # Importa services necessários
            from src.services.service_providers import (
                session_service,
                artifacts_service,
                memory_service,
            )

            # Chama agent_runner diretamente (sem task manager)
            logger.info("🔄 Calling agent_runner directly...")

            from src.services.adk.agent_runner import run_agent

            result = await run_agent(
                agent_id=str(self.agent_id),
                external_id=session_id,
                message=message_text,
                session_service=session_service,
                artifacts_service=artifacts_service,
                memory_service=memory_service,
                db=self.db,
                files=None,  # TODO: processar files se necessário
            )

            logger.info(f"✅ Agent result: {result}")

            # Converte resultado para evento SDK
            final_response = result.get("final_response", "No response")

            # Cria mensagem de resposta compatível com SDK
            response_message = new_agent_text_message(final_response)
            event_queue.enqueue_event(response_message)

            logger.info("✅ Response message enqueued successfully")

        except Exception as e:
            logger.error(f"❌ ERROR in execute(): {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            await self._emit_error_event(event_queue, f"Execution error: {str(e)}")

    def _extract_text_from_message(self, message) -> str:
        """Extrai texto da mensagem SDK."""
        try:
            logger.info(f"🔍 DEBUG MESSAGE STRUCTURE:")
            logger.info(f"Message type: {type(message)}")
            logger.info(f"Message: {message}")
            logger.info(f"Message hasattr parts: {hasattr(message, 'parts')}")

            if hasattr(message, "parts"):
                logger.info(f"Parts: {message.parts}")
                logger.info(f"Parts type: {type(message.parts)}")
                logger.info(
                    f"Parts length: {len(message.parts) if message.parts else 0}"
                )

                if message.parts:
                    for i, part in enumerate(message.parts):
                        logger.info(f"Part {i}: type={type(part)}, content={part}")
                        logger.info(f"Part {i} hasattr text: {hasattr(part, 'text')}")
                        if hasattr(part, "text"):
                            logger.info(f"Part {i} text: {part.text}")
                            return part.text

            # Tenta outras formas de acessar o texto
            if hasattr(message, "text"):
                logger.info(f"Message has direct text: {message.text}")
                return message.text

            # Se for string diretamente
            if isinstance(message, str):
                logger.info(f"Message is string: {message}")
                return message

            logger.warning("❌ No text found in any format")
            return ""
        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return ""

    async def _emit_error_event(self, event_queue: "EventQueue", error_message: str):
        """Emite evento de erro."""
        try:
            error_msg = new_agent_text_message(f"Error: {error_message}")
            event_queue.enqueue_event(error_msg)
        except Exception as e:
            logger.error(f"Error emitting error event: {e}")

    async def cancel(
        self, context: "RequestContext", event_queue: "EventQueue"
    ) -> None:
        """Implementa cancelamento (básico por enquanto)."""
        logger.info(f"Cancel called for agent {self.agent_id}")
        # Por enquanto, só log - implementar cancelamento real se necessário


class EvoAISDKService:
    """
    Serviço principal que cria e gerencia servidores A2A usando o SDK oficial.
    """

    def __init__(self, db: Session):
        self.db = db
        self.servers: Dict[str, Any] = {}

    def create_a2a_server(self, agent_id: UUID) -> Optional[Any]:
        """
        Cria um servidor A2A usando o SDK oficial mas com lógica interna.
        """
        if not SDK_AVAILABLE:
            logger.error("❌ a2a-sdk not available, cannot create SDK server")
            return None

        try:
            logger.info("=" * 80)
            logger.info(f"🏗️ CREATING A2A SDK SERVER FOR AGENT {agent_id}")
            logger.info("=" * 80)

            # Busca agent
            logger.info("🔍 Searching for agent in database...")
            agent = get_agent(self.db, agent_id)
            if not agent:
                logger.error(f"❌ Agent {agent_id} not found")
                return None

            logger.info(f"✅ Found agent: {agent.name}")

            # Cria agent card usando lógica existente
            logger.info("🏗️ Creating agent card...")
            agent_card = self._create_agent_card(agent)
            logger.info(f"✅ Agent card created: {agent_card.name}")

            # Cria executor usando adapter
            logger.info("🏗️ Creating agent executor adapter...")
            agent_executor = EvoAIAgentExecutor(self.db, agent_id)
            logger.info("✅ Agent executor created")

            # Cria task store
            logger.info("🏗️ Creating task store...")
            task_store = InMemoryTaskStore()
            logger.info("✅ Task store created")

            # Cria request handler
            logger.info("🏗️ Creating request handler...")
            request_handler = DefaultRequestHandler(
                agent_executor=agent_executor, task_store=task_store
            )
            logger.info("✅ Request handler created")

            # Cria aplicação Starlette
            logger.info("🏗️ Creating Starlette application...")
            server = A2AStarletteApplication(
                agent_card=agent_card, http_handler=request_handler
            )
            logger.info("✅ Starlette application created")

            # Armazena servidor
            server_key = str(agent_id)
            self.servers[server_key] = server

            logger.info("=" * 80)
            logger.info(f"🎉 SUCCESSFULLY CREATED A2A SDK SERVER FOR AGENT {agent_id}")
            logger.info("=" * 80)
            return server

        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"❌ ERROR CREATING A2A SDK SERVER: {e}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            logger.error("=" * 80)
            return None

    def get_server(self, agent_id: UUID) -> Optional[Any]:
        """
        Retorna servidor existente ou cria um novo.
        """
        server_key = str(agent_id)

        if server_key in self.servers:
            return self.servers[server_key]

        return self.create_a2a_server(agent_id)

    def _create_agent_card(self, agent) -> AgentCard:
        """
        Cria AgentCard usando lógica existente mas no formato SDK.
        """
        # Reutiliza lógica do A2AService existente
        a2a_service = A2AService(self.db, A2ATaskManager(self.db))
        custom_card = a2a_service.get_agent_card(agent.id)

        # Converte para formato SDK
        sdk_card = convert_to_sdk_format(custom_card)

        if sdk_card:
            return sdk_card

        # Fallback: cria card básico
        return AgentCard(
            name=agent.name,
            description=agent.description or "",
            url=f"{settings.API_URL}/api/v1/a2a-sdk/{agent.id}",
            version=settings.API_VERSION,
            capabilities=AgentCapabilities(
                streaming=True, pushNotifications=False, stateTransitionHistory=True
            ),
            provider=AgentProvider(
                organization=settings.ORGANIZATION_NAME, url=settings.ORGANIZATION_URL
            ),
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            skills=[],
        )

    def remove_server(self, agent_id: UUID) -> bool:
        """
        Remove servidor do cache.
        """
        server_key = str(agent_id)
        if server_key in self.servers:
            del self.servers[server_key]
            return True
        return False

    def list_servers(self) -> Dict[str, Dict[str, Any]]:
        """
        Lista todos os servidores ativos.
        """
        result = {}
        for agent_id, server in self.servers.items():
            result[agent_id] = {
                "agent_id": agent_id,
                "server_type": "a2a-sdk",
                "active": True,
            }
        return result


# Função utilitária para criar servidor SDK facilmente
def create_a2a_sdk_server(db: Session, agent_id: UUID) -> Optional[Any]:
    """
    Função utilitária para criar servidor A2A usando SDK.
    """
    service = EvoAISDKService(db)
    return service.create_a2a_server(agent_id)


# Função para verificar compatibilidade
def check_sdk_compatibility() -> Dict[str, Any]:
    """
    Verifica compatibilidade e funcionalidades disponíveis do SDK.
    """
    return {
        "sdk_available": SDK_AVAILABLE,
        "version": (
            getattr(settings, "A2A_SDK_VERSION", "unknown") if SDK_AVAILABLE else None
        ),
        "features": {
            "streaming": SDK_AVAILABLE,
            "task_management": SDK_AVAILABLE,
            "agent_execution": SDK_AVAILABLE,
            "type_validation": SDK_AVAILABLE,
        },
    }
