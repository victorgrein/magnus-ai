import logging
import httpx
from httpx_sse import connect_sse
from typing import Any, AsyncIterable, Optional
from docs.A2A.samples.python.common.types import (
    AgentCard,
    GetTaskRequest,
    SendTaskRequest,
    SendTaskResponse,
    JSONRPCRequest,
    GetTaskResponse,
    CancelTaskResponse,
    CancelTaskRequest,
    SetTaskPushNotificationRequest,
    SetTaskPushNotificationResponse,
    GetTaskPushNotificationRequest,
    GetTaskPushNotificationResponse,
    A2AClientHTTPError,
    A2AClientJSONError,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
)
import json
import asyncio
import uuid


# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("a2a_client_runner")


class A2ACardResolver:
    def __init__(self, base_url, agent_card_path="/.well-known/agent.json"):
        self.base_url = base_url.rstrip("/")
        self.agent_card_path = agent_card_path.lstrip("/")

    def get_agent_card(self) -> AgentCard:
        with httpx.Client() as client:
            response = client.get(self.base_url + "/" + self.agent_card_path)
            response.raise_for_status()
            try:
                return AgentCard(**response.json())
            except json.JSONDecodeError as e:
                raise A2AClientJSONError(str(e)) from e


class A2AClient:
    def __init__(
        self,
        agent_card: AgentCard = None,
        url: str = None,
        api_key: Optional[str] = None,
    ):
        if agent_card:
            self.url = agent_card.url
        elif url:
            self.url = url
        else:
            raise ValueError("Must provide either agent_card or url")
        self.api_key = api_key
        self.headers = {"x-api-key": api_key} if api_key else {}

    async def send_task(self, payload: dict[str, Any]) -> SendTaskResponse:
        request = SendTaskRequest(params=payload)
        return SendTaskResponse(**await self._send_request(request))

    async def send_task_streaming(
        self, payload: dict[str, Any]
    ) -> AsyncIterable[SendTaskStreamingResponse]:
        request = SendTaskStreamingRequest(params=payload)
        with httpx.Client(timeout=None) as client:
            with connect_sse(
                client,
                "POST",
                self.url,
                json=request.model_dump(),
                headers=self.headers,
            ) as event_source:
                try:
                    for sse in event_source.iter_sse():
                        yield SendTaskStreamingResponse(**json.loads(sse.data))
                except json.JSONDecodeError as e:
                    raise A2AClientJSONError(str(e)) from e
                except httpx.RequestError as e:
                    raise A2AClientHTTPError(400, str(e)) from e

    async def _send_request(self, request: JSONRPCRequest) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                # Image generation could take time, adding timeout
                response = await client.post(
                    self.url,
                    json=request.model_dump(),
                    headers=self.headers,
                    timeout=30,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise A2AClientHTTPError(e.response.status_code, str(e)) from e
            except json.JSONDecodeError as e:
                raise A2AClientJSONError(str(e)) from e

    async def get_task(self, payload: dict[str, Any]) -> GetTaskResponse:
        request = GetTaskRequest(params=payload)
        return GetTaskResponse(**await self._send_request(request))

    async def cancel_task(self, payload: dict[str, Any]) -> CancelTaskResponse:
        request = CancelTaskRequest(params=payload)
        return CancelTaskResponse(**await self._send_request(request))

    async def set_task_callback(
        self, payload: dict[str, Any]
    ) -> SetTaskPushNotificationResponse:
        request = SetTaskPushNotificationRequest(params=payload)
        return SetTaskPushNotificationResponse(**await self._send_request(request))

    async def get_task_callback(
        self, payload: dict[str, Any]
    ) -> GetTaskPushNotificationResponse:
        request = GetTaskPushNotificationRequest(params=payload)
        return GetTaskPushNotificationResponse(**await self._send_request(request))


async def main():
    # Configurações
    BASE_URL = "http://localhost:8000/api/v1/a2a/18a2889e-8573-4e70-833c-7d9e00a8fd80"
    API_KEY = "83c2c19f-dc2e-4abe-9a41-ef7d2eb079d6"

    try:
        # Obter o card do agente
        logger.info("Obtendo card do agente...")
        card_resolver = A2ACardResolver(BASE_URL)
        try:
            card = card_resolver.get_agent_card()
            logger.info(f"Card do agente: {card}")
        except Exception as e:
            logger.error(f"Erro ao obter card do agente: {e}")
            return

        # Criar cliente A2A com API key
        client = A2AClient(card, api_key=API_KEY)

        # Exemplo 1: Enviar tarefa síncrona
        logger.info("\n=== TESTE DE TAREFA SÍNCRONA ===")
        task_id = str(uuid.uuid4())
        session_id = "test-session-1"

        # Preparar payload da tarefa
        payload = {
            "id": task_id,
            "sessionId": session_id,
            "message": {
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": "Quais são os três maiores países do mundo em área territorial?",
                    }
                ],
            },
        }

        logger.info(f"Enviando tarefa com ID: {task_id}")
        async for streaming_response in client.send_task_streaming(payload):
            if hasattr(streaming_response.result, "artifact"):
                # Processar conteúdo parcial
                print(streaming_response.result.artifact.parts[0].text)
            elif (
                hasattr(streaming_response.result, "status")
                and streaming_response.result.status.state == "completed"
            ):
                # Tarefa concluída
                print(
                    "Resposta final:",
                    streaming_response.result.status.message.parts[0].text,
                )

    except Exception as e:
        logger.error(f"Erro durante execução dos testes: {e}")


if __name__ == "__main__":
    asyncio.run(main())
