import uuid
import json
from typing import AsyncGenerator, Dict, Any
from fastapi import HTTPException
from datetime import datetime
from ..schemas.streaming import (
    JSONRPCRequest,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
)
from ..services.agent_runner import run_agent
from ..services.service_providers import (
    session_service,
    artifacts_service,
    memory_service,
)
from sqlalchemy.orm import Session


class StreamingService:
    def __init__(self):
        self.active_connections: Dict[str, Any] = {}

    async def send_task_streaming(
        self,
        agent_id: str,
        api_key: str,
        message: str,
        session_id: str = None,
        db: Session = None,
    ) -> AsyncGenerator[str, None]:
        """
        Inicia o streaming de eventos SSE para uma tarefa.

        Args:
            agent_id: ID do agente
            api_key: Chave de API para autenticação
            message: Mensagem inicial
            session_id: ID da sessão (opcional)
            db: Sessão do banco de dados

        Yields:
            Eventos SSE formatados
        """
        # Validação básica da API key
        if not api_key:
            raise HTTPException(status_code=401, detail="API key é obrigatória")

        # Gera IDs únicos
        task_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        # Monta payload JSON-RPC
        payload = JSONRPCRequest(
            id=request_id,
            params={
                "id": task_id,
                "sessionId": session_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": message}],
                },
            },
        )

        # Registra conexão
        self.active_connections[task_id] = {
            "agent_id": agent_id,
            "api_key": api_key,
            "session_id": session_id,
        }

        try:
            # Envia evento de início
            yield self._format_sse_event(
                "status",
                TaskStatusUpdateEvent(
                    state="working",
                    timestamp=datetime.now().isoformat(),
                    message=payload.params["message"],
                ).model_dump_json(),
            )

            # Executa o agente
            result = await run_agent(
                str(agent_id),
                task_id,
                message,
                session_service,
                artifacts_service,
                memory_service,
                db,
                session_id,
            )

            # Envia a resposta do agente como um evento separado
            yield self._format_sse_event(
                "message",
                json.dumps(
                    {
                        "role": "agent",
                        "content": result,
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
            )

            # Evento de conclusão
            yield self._format_sse_event(
                "status",
                TaskStatusUpdateEvent(
                    state="completed",
                    timestamp=datetime.now().isoformat(),
                ).model_dump_json(),
            )

        except Exception as e:
            # Evento de erro
            yield self._format_sse_event(
                "status",
                TaskStatusUpdateEvent(
                    state="failed",
                    timestamp=datetime.now().isoformat(),
                    error={"message": str(e)},
                ).model_dump_json(),
            )
            raise

        finally:
            # Limpa conexão
            self.active_connections.pop(task_id, None)

    def _format_sse_event(self, event_type: str, data: str) -> str:
        """Formata um evento SSE."""
        return f"event: {event_type}\ndata: {data}\n\n"

    async def close_connection(self, task_id: str):
        """Fecha uma conexão de streaming."""
        if task_id in self.active_connections:
            self.active_connections.pop(task_id)
