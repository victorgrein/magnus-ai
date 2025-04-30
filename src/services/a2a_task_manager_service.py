"""
A2A Task Manager Service.

This service implements task management for the A2A protocol, handling task lifecycle
including execution, streaming, push notifications, status queries, and cancellation.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, AsyncIterable

from sqlalchemy.orm import Session

from src.schemas.a2a.exceptions import (
    TaskNotFoundError,
    TaskNotCancelableError,
    PushNotificationNotSupportedError,
    InternalError,
    ContentTypeNotSupportedError,
)

from src.schemas.a2a.types import (
    JSONRPCResponse,
    TaskIdParams,
    TaskQueryParams,
    GetTaskRequest,
    SendTaskRequest,
    CancelTaskRequest,
    SetTaskPushNotificationRequest,
    GetTaskPushNotificationRequest,
    GetTaskResponse,
    CancelTaskResponse,
    SendTaskResponse,
    SetTaskPushNotificationResponse,
    GetTaskPushNotificationResponse,
    TaskSendParams,
    TaskStatus,
    TaskState,
    TaskResubscriptionRequest,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
    Artifact,
    PushNotificationConfig,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    JSONRPCError,
    TaskPushNotificationConfig,
    Message,
    TextPart,
    Task,
)
from src.services.redis_cache_service import RedisCacheService
from src.utils.a2a_utils import (
    are_modalities_compatible,
    new_incompatible_types_error,
    new_not_implemented_error,
    create_task_id,
    format_error_response,
)

logger = logging.getLogger(__name__)


class A2ATaskManager:
    """
    A2A Task Manager implementation.

    This class manages the lifecycle of A2A tasks, including:
    - Task submission and execution
    - Task status queries
    - Task cancellation
    - Push notification configuration
    - SSE streaming for real-time updates
    """

    def __init__(
        self,
        redis_cache: RedisCacheService,
        agent_runner=None,
        streaming_service=None,
        push_notification_service=None,
        db=None,
    ):
        """
        Initialize the A2A Task Manager.

        Args:
            redis_cache: Redis cache service for task storage
            agent_runner: Agent runner service for task execution
            streaming_service: Streaming service for SSE
            push_notification_service: Service for push notifications
            db: Database session
        """
        self.redis_cache = redis_cache
        self.agent_runner = agent_runner
        self.streaming_service = streaming_service
        self.push_notification_service = push_notification_service
        self.db = db
        self.lock = asyncio.Lock()
        self.subscriber_lock = asyncio.Lock()
        self.task_sse_subscribers = {}

    async def on_get_task(self, request: GetTaskRequest) -> GetTaskResponse:
        """
        Manipula requisição para obter informações sobre uma tarefa.

        Args:
            request: Requisição Get Task do A2A

        Returns:
            Resposta com os detalhes da tarefa
        """
        try:
            task_id = request.params.id
            history_length = request.params.historyLength

            # Busca dados da tarefa do cache
            task_data = await self.redis_cache.get(f"task:{task_id}")

            if not task_data:
                logger.warning(f"Tarefa não encontrada: {task_id}")
                return GetTaskResponse(id=request.id, error=TaskNotFoundError())

            # Cria uma instância Task a partir dos dados do cache
            task = Task.model_validate(task_data)

            # Se o parâmetro historyLength estiver presente, manipula o histórico
            if history_length is not None and task.history:
                if history_length == 0:
                    task.history = []
                elif len(task.history) > history_length:
                    task.history = task.history[-history_length:]

            return GetTaskResponse(id=request.id, result=task)
        except Exception as e:
            logger.error(f"Erro ao processar on_get_task: {str(e)}")
            return GetTaskResponse(id=request.id, error=InternalError(message=str(e)))

    async def on_cancel_task(self, request: CancelTaskRequest) -> CancelTaskResponse:
        """
        Handle request to cancel a running task.

        Args:
            request: The JSON-RPC request to cancel a task

        Returns:
            Response with updated task data or error
        """
        logger.info(f"Cancelling task {request.params.id}")
        task_id_params = request.params

        try:
            task_data = await self.redis_cache.get(f"task:{task_id_params.id}")
            if not task_data:
                logger.warning(f"Task {task_id_params.id} not found for cancellation")
                return CancelTaskResponse(id=request.id, error=TaskNotFoundError())

            # Check if task can be cancelled
            current_state = task_data.get("status", {}).get("state")
            if current_state not in [TaskState.SUBMITTED, TaskState.WORKING]:
                logger.warning(
                    f"Task {task_id_params.id} in state {current_state} cannot be cancelled"
                )
                return CancelTaskResponse(id=request.id, error=TaskNotCancelableError())

            # Update task status to cancelled
            task_data["status"] = {
                "state": TaskState.CANCELED,
                "timestamp": datetime.now().isoformat(),
                "message": {
                    "role": "agent",
                    "parts": [{"type": "text", "text": "Task cancelled by user"}],
                },
            }

            # Save updated task data
            await self.redis_cache.set(f"task:{task_id_params.id}", task_data)

            # Send push notification if configured
            await self._send_push_notification_for_task(
                task_id_params.id, "canceled", system_message="Task cancelled by user"
            )

            # Publish event to SSE subscribers
            await self._publish_task_update(
                task_id_params.id,
                TaskStatusUpdateEvent(
                    id=task_id_params.id,
                    status=TaskStatus(
                        state=TaskState.CANCELED,
                        timestamp=datetime.now(),
                        message=Message(
                            role="agent",
                            parts=[TextPart(text="Task cancelled by user")],
                        ),
                    ),
                    final=True,
                ),
            )

            return CancelTaskResponse(id=request.id, result=task_data)

        except Exception as e:
            logger.error(f"Error cancelling task: {str(e)}", exc_info=True)
            return CancelTaskResponse(
                id=request.id,
                error=InternalError(message=f"Error cancelling task: {str(e)}"),
            )

    async def on_send_task(self, request: SendTaskRequest) -> SendTaskResponse:
        """
        Manipula requisição para enviar uma nova tarefa.

        Args:
            request: Requisição de envio de tarefa

        Returns:
            Resposta com os detalhes da tarefa criada
        """
        try:
            params = request.params
            task_id = params.id
            logger.info(f"Recebendo tarefa {task_id}")

            # Verifica se já existe uma tarefa com esse ID
            existing_task = await self.redis_cache.get(f"task:{task_id}")
            if existing_task:
                # Se a tarefa já existe e está em progresso, retorna a tarefa atual
                if existing_task.get("status", {}).get("state") in [
                    TaskState.WORKING,
                    TaskState.COMPLETED,
                ]:
                    logger.info(
                        f"Tarefa {task_id} já existe e está em progresso/concluída"
                    )
                    return SendTaskResponse(
                        id=request.id, result=Task.model_validate(existing_task)
                    )

                # Se a tarefa existe mas falhou ou foi cancelada, podemos reprocessá-la
                logger.info(f"Reprocessando tarefa existente {task_id}")

            # Verifica compatibilidade de modalidades
            server_output_modes = []
            if self.agent_runner:
                # Tenta obter modos suportados do agente
                try:
                    server_output_modes = await self.agent_runner.get_supported_modes()
                except Exception as e:
                    logger.warning(f"Erro ao obter modos suportados: {str(e)}")
                    server_output_modes = ["text"]  # Fallback para texto

            if not are_modalities_compatible(
                server_output_modes, params.acceptedOutputModes
            ):
                logger.warning(
                    f"Modos incompatíveis: servidor={server_output_modes}, cliente={params.acceptedOutputModes}"
                )
                return SendTaskResponse(
                    id=request.id, error=ContentTypeNotSupportedError()
                )

            # Cria dados da tarefa
            task_data = await self._create_task_data(params)

            # Armazena a tarefa no cache
            await self.redis_cache.set(f"task:{task_id}", task_data)

            # Configura notificações push, se fornecidas
            if params.pushNotification:
                await self.redis_cache.set(
                    f"task_notification:{task_id}", params.pushNotification.model_dump()
                )

            # Inicia a execução da tarefa em background
            asyncio.create_task(self._execute_task(task_data, params))

            # Converte para objeto Task e retorna
            task = Task.model_validate(task_data)
            return SendTaskResponse(id=request.id, result=task)

        except Exception as e:
            logger.error(f"Erro ao processar on_send_task: {str(e)}")
            return SendTaskResponse(id=request.id, error=InternalError(message=str(e)))

    async def on_send_task_subscribe(
        self, request: SendTaskStreamingRequest
    ) -> Union[AsyncIterable[SendTaskStreamingResponse], JSONRPCResponse]:
        """
        Handle request to send a task and subscribe to streaming updates.

        Args:
            request: The JSON-RPC request to send a task with streaming

        Returns:
            Stream of events or error response
        """
        logger.info(f"Sending task with streaming {request.params.id}")
        task_send_params = request.params

        try:
            # Check output mode compatibility
            if not are_modalities_compatible(
                ["text", "application/json"],  # Default supported modes
                task_send_params.acceptedOutputModes,
            ):
                return new_incompatible_types_error(request.id)

            # Create initial task data
            task_data = await self._create_task_data(task_send_params)

            # Setup SSE consumer
            sse_queue = await self._setup_sse_consumer(task_send_params.id)

            # Execute task asynchronously (fire and forget)
            asyncio.create_task(self._execute_task(task_data, task_send_params))

            # Return generator to dequeue events for SSE
            return self._dequeue_events_for_sse(
                request.id, task_send_params.id, sse_queue
            )

        except Exception as e:
            logger.error(f"Error setting up streaming task: {str(e)}", exc_info=True)
            return SendTaskStreamingResponse(
                id=request.id,
                error=InternalError(
                    message=f"Error setting up streaming task: {str(e)}"
                ),
            )

    async def on_set_task_push_notification(
        self, request: SetTaskPushNotificationRequest
    ) -> SetTaskPushNotificationResponse:
        """
        Configure push notifications for a task.

        Args:
            request: The JSON-RPC request to set push notification

        Returns:
            Response with configuration or error
        """
        logger.info(f"Setting push notification for task {request.params.id}")
        task_notification_params = request.params

        try:
            if not self.push_notification_service:
                logger.warning("Push notifications not supported")
                return SetTaskPushNotificationResponse(
                    id=request.id, error=PushNotificationNotSupportedError()
                )

            # Check if task exists
            task_data = await self.redis_cache.get(
                f"task:{task_notification_params.id}"
            )
            if not task_data:
                logger.warning(
                    f"Task {task_notification_params.id} not found for setting push notification"
                )
                return SetTaskPushNotificationResponse(
                    id=request.id, error=TaskNotFoundError()
                )

            # Save push notification config
            config = {
                "url": task_notification_params.pushNotificationConfig.url,
                "headers": {},  # Add auth headers if needed
            }

            await self.redis_cache.set(
                f"task:{task_notification_params.id}:push", config
            )

            return SetTaskPushNotificationResponse(
                id=request.id, result=task_notification_params
            )

        except Exception as e:
            logger.error(f"Error setting push notification: {str(e)}", exc_info=True)
            return SetTaskPushNotificationResponse(
                id=request.id,
                error=InternalError(
                    message=f"Error setting push notification: {str(e)}"
                ),
            )

    async def on_get_task_push_notification(
        self, request: GetTaskPushNotificationRequest
    ) -> GetTaskPushNotificationResponse:
        """
        Get push notification configuration for a task.

        Args:
            request: The JSON-RPC request to get push notification config

        Returns:
            Response with configuration or error
        """
        logger.info(f"Getting push notification for task {request.params.id}")
        task_params = request.params

        try:
            if not self.push_notification_service:
                logger.warning("Push notifications not supported")
                return GetTaskPushNotificationResponse(
                    id=request.id, error=PushNotificationNotSupportedError()
                )

            # Check if task exists
            task_data = await self.redis_cache.get(f"task:{task_params.id}")
            if not task_data:
                logger.warning(
                    f"Task {task_params.id} not found for getting push notification"
                )
                return GetTaskPushNotificationResponse(
                    id=request.id, error=TaskNotFoundError()
                )

            # Get push notification config
            config = await self.redis_cache.get(f"task:{task_params.id}:push")
            if not config:
                logger.warning(f"No push notification config for task {task_params.id}")
                return GetTaskPushNotificationResponse(
                    id=request.id,
                    error=InternalError(
                        message="No push notification configuration found"
                    ),
                )

            result = TaskPushNotificationConfig(
                id=task_params.id,
                pushNotificationConfig=PushNotificationConfig(
                    url=config.get("url"), token=None, authentication=None
                ),
            )

            return GetTaskPushNotificationResponse(id=request.id, result=result)

        except Exception as e:
            logger.error(f"Error getting push notification: {str(e)}", exc_info=True)
            return GetTaskPushNotificationResponse(
                id=request.id,
                error=InternalError(
                    message=f"Error getting push notification: {str(e)}"
                ),
            )

    async def on_resubscribe_to_task(
        self, request: TaskResubscriptionRequest
    ) -> Union[AsyncIterable[SendTaskStreamingResponse], JSONRPCResponse]:
        """
        Resubscribe to a task's streaming events.

        Args:
            request: The JSON-RPC request to resubscribe

        Returns:
            Stream of events or error response
        """
        logger.info(f"Resubscribing to task {request.params.id}")
        task_params = request.params

        try:
            # Check if task exists
            task_data = await self.redis_cache.get(f"task:{task_params.id}")
            if not task_data:
                logger.warning(f"Task {task_params.id} not found for resubscription")
                return JSONRPCResponse(id=request.id, error=TaskNotFoundError())

            # Setup SSE consumer with resubscribe flag
            try:
                sse_queue = await self._setup_sse_consumer(
                    task_params.id, is_resubscribe=True
                )
            except ValueError:
                logger.warning(
                    f"Task {task_params.id} not available for resubscription"
                )
                return JSONRPCResponse(
                    id=request.id,
                    error=InternalError(
                        message="Task not available for resubscription"
                    ),
                )

            # Send initial status update to the new subscriber
            status = task_data.get("status", {})
            final = status.get("state") in [
                TaskState.COMPLETED,
                TaskState.FAILED,
                TaskState.CANCELED,
            ]

            # Convert to TaskStatus object
            task_status = TaskStatus(
                state=status.get("state", TaskState.UNKNOWN),
                timestamp=datetime.fromisoformat(
                    status.get("timestamp", datetime.now().isoformat())
                ),
                message=status.get("message"),
            )

            # Publish to the specific queue
            await sse_queue.put(
                TaskStatusUpdateEvent(
                    id=task_params.id, status=task_status, final=final
                )
            )

            # Return generator to dequeue events for SSE
            return self._dequeue_events_for_sse(request.id, task_params.id, sse_queue)

        except Exception as e:
            logger.error(f"Error resubscribing to task: {str(e)}", exc_info=True)
            return JSONRPCResponse(
                id=request.id,
                error=InternalError(message=f"Error resubscribing to task: {str(e)}"),
            )

    async def _create_task_data(self, params: TaskSendParams) -> Dict[str, Any]:
        """
        Create initial task data structure.

        Args:
            params: Task send parameters

        Returns:
            Task data dictionary
        """
        # Create task with initial status
        task_data = {
            "id": params.id,
            "sessionId": params.sessionId,
            "status": {
                "state": TaskState.SUBMITTED,
                "timestamp": datetime.now().isoformat(),
                "message": None,
                "error": None,
            },
            "artifacts": [],
            "history": [params.message.model_dump()],
            "metadata": params.metadata or {},
        }

        # Save task data
        await self.redis_cache.set(f"task:{params.id}", task_data)

        return task_data

    async def _execute_task(self, task: Dict[str, Any], params: TaskSendParams) -> None:
        """
        Executa uma tarefa usando o adaptador do agente.

        Esta função é responsável pela execução real da tarefa pelo agente,
        atualizando seu status conforme o progresso.

        Args:
            task: Dados da tarefa a ser executada
            params: Parâmetros de envio da tarefa
        """
        task_id = task["id"]
        agent_id = params.agentId
        message_text = ""

        # Extrai o texto da mensagem
        if params.message and params.message.parts:
            for part in params.message.parts:
                if part.type == "text":
                    message_text += part.text

        if not message_text:
            await self._update_task_status(
                task_id, TaskState.FAILED, "Mensagem não contém texto", final=True
            )
            return

        # Verificamos se é uma execução em andamento
        task_status = task.get("status", {})
        if task_status.get("state") in [TaskState.WORKING, TaskState.COMPLETED]:
            logger.info(f"Tarefa {task_id} já está em execução ou concluída")
            return

        try:
            # Atualiza para estado "working"
            await self._update_task_status(
                task_id, TaskState.WORKING, "Processando solicitação"
            )

            # Executa o agente
            if self.agent_runner:
                response = await self.agent_runner.run_agent(
                    agent_id=agent_id,
                    message=message_text,
                    session_id=params.sessionId,
                    task_id=task_id,
                )

                # Processa a resposta do agente
                if response and isinstance(response, dict):
                    # Extrai texto da resposta
                    response_text = response.get("content", "")
                    if not response_text and "message" in response:
                        message = response.get("message", {})
                        parts = message.get("parts", [])
                        for part in parts:
                            if part.get("type") == "text":
                                response_text += part.get("text", "")

                    # Constrói a mensagem final do agente
                    if response_text:
                        # Cria um artefato para a resposta
                        artifact = Artifact(
                            name="response",
                            parts=[TextPart(text=response_text)],
                            index=0,
                            lastChunk=True,
                        )

                        # Adiciona o artefato à tarefa
                        await self._add_task_artifact(task_id, artifact)

                        # Atualiza o status da tarefa para completado
                        await self._update_task_status(
                            task_id, TaskState.COMPLETED, response_text, final=True
                        )
                    else:
                        await self._update_task_status(
                            task_id,
                            TaskState.FAILED,
                            "O agente não retornou uma resposta válida",
                            final=True,
                        )
                else:
                    await self._update_task_status(
                        task_id,
                        TaskState.FAILED,
                        "Resposta inválida do agente",
                        final=True,
                    )
            else:
                await self._update_task_status(
                    task_id,
                    TaskState.FAILED,
                    "Adaptador do agente não configurado",
                    final=True,
                )
        except Exception as e:
            logger.error(f"Erro na execução da tarefa {task_id}: {str(e)}")
            await self._update_task_status(
                task_id, TaskState.FAILED, f"Erro ao processar: {str(e)}", final=True
            )

    async def _update_task_status(
        self, task_id: str, state: TaskState, message_text: str, final: bool = False
    ) -> None:
        """
        Atualiza o status de uma tarefa.

        Args:
            task_id: ID da tarefa a ser atualizada
            state: Novo estado da tarefa
            message_text: Texto da mensagem associada ao status
            final: Indica se este é o status final da tarefa
        """
        try:
            # Busca dados atuais da tarefa
            task_data = await self.redis_cache.get(f"task:{task_id}")
            if not task_data:
                logger.warning(
                    f"Não foi possível atualizar status: tarefa {task_id} não encontrada"
                )
                return

            # Cria objeto de status com a mensagem
            agent_message = Message(
                role="agent",
                parts=[TextPart(text=message_text)],
                metadata={"timestamp": datetime.now().isoformat()},
            )

            status = TaskStatus(
                state=state, message=agent_message, timestamp=datetime.now()
            )

            # Atualiza o status na tarefa
            task_data["status"] = status.model_dump(exclude_none=True)

            # Atualiza o histórico, se existir
            if "history" not in task_data:
                task_data["history"] = []

            # Adiciona a mensagem ao histórico
            task_data["history"].append(agent_message.model_dump(exclude_none=True))

            # Armazena a tarefa atualizada
            await self.redis_cache.set(f"task:{task_id}", task_data)

            # Cria evento de atualização de status
            status_event = TaskStatusUpdateEvent(id=task_id, status=status, final=final)

            # Publica atualização
            await self._publish_task_update(task_id, status_event)

            # Envia notificação push, se configurada
            if final or state in [
                TaskState.FAILED,
                TaskState.COMPLETED,
                TaskState.CANCELED,
            ]:
                await self._send_push_notification_for_task(
                    task_id=task_id, state=state, message_text=message_text
                )
        except Exception as e:
            logger.error(f"Erro ao atualizar status da tarefa {task_id}: {str(e)}")

    async def _add_task_artifact(self, task_id: str, artifact: Artifact) -> None:
        """
        Add an artifact to a task and publish the update.

        Args:
            task_id: Task ID
            artifact: Artifact to add
        """
        logger.info(f"Adding artifact to task {task_id}")

        # Update task data
        task_data = await self.redis_cache.get(f"task:{task_id}")
        if task_data:
            if "artifacts" not in task_data:
                task_data["artifacts"] = []

            # Convert artifact to dict
            artifact_dict = artifact.model_dump()
            task_data["artifacts"].append(artifact_dict)
            await self.redis_cache.set(f"task:{task_id}", task_data)

        # Create artifact update event
        event = TaskArtifactUpdateEvent(id=task_id, artifact=artifact)

        # Publish event
        await self._publish_task_update(task_id, event)

    async def _publish_task_update(
        self, task_id: str, event: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent]
    ) -> None:
        """
        Publish a task update event to all subscribers.

        Args:
            task_id: Task ID
            event: Event to publish
        """
        async with self.subscriber_lock:
            if task_id not in self.task_sse_subscribers:
                return

            subscribers = self.task_sse_subscribers[task_id]
            for subscriber in subscribers:
                try:
                    await subscriber.put(event)
                except Exception as e:
                    logger.error(f"Error publishing event to subscriber: {str(e)}")

    async def _send_push_notification_for_task(
        self,
        task_id: str,
        state: str,
        message_text: str = None,
        system_message: str = None,
    ) -> None:
        """
        Send push notification for a task if configured.

        Args:
            task_id: Task ID
            state: Task state
            message_text: Optional message text
            system_message: Optional system message
        """
        if not self.push_notification_service:
            return

        try:
            # Get push notification config
            config = await self.redis_cache.get(f"task:{task_id}:push")
            if not config:
                return

            # Create message if provided
            message = None
            if message_text:
                message = {
                    "role": "agent",
                    "parts": [{"type": "text", "text": message_text}],
                }
            elif system_message:
                # We use 'agent' instead of 'system' since Message only accepts 'user' or 'agent'
                message = {
                    "role": "agent",
                    "parts": [{"type": "text", "text": system_message}],
                }

            # Send notification
            await self.push_notification_service.send_notification(
                url=config["url"],
                task_id=task_id,
                state=state,
                message=message,
                headers=config.get("headers", {}),
            )

        except Exception as e:
            logger.error(
                f"Error sending push notification for task {task_id}: {str(e)}"
            )

    async def _setup_sse_consumer(
        self, task_id: str, is_resubscribe: bool = False
    ) -> asyncio.Queue:
        """
        Set up an SSE consumer queue for a task.

        Args:
            task_id: Task ID
            is_resubscribe: Whether this is a resubscription

        Returns:
            Queue for events

        Raises:
            ValueError: If resubscribing to non-existent task
        """
        async with self.subscriber_lock:
            if task_id not in self.task_sse_subscribers:
                if is_resubscribe:
                    raise ValueError("Task not found for resubscription")
                self.task_sse_subscribers[task_id] = []

            queue = asyncio.Queue()
            self.task_sse_subscribers[task_id].append(queue)
            return queue

    async def _dequeue_events_for_sse(
        self, request_id: str, task_id: str, event_queue: asyncio.Queue
    ) -> AsyncIterable[SendTaskStreamingResponse]:
        """
        Dequeue and yield events for SSE streaming.

        Args:
            request_id: Request ID
            task_id: Task ID
            event_queue: Queue for events

        Yields:
            SSE events wrapped in SendTaskStreamingResponse
        """
        try:
            while True:
                event = await event_queue.get()

                if isinstance(event, JSONRPCError):
                    yield SendTaskStreamingResponse(id=request_id, error=event)
                    break

                yield SendTaskStreamingResponse(id=request_id, result=event)

                # Check if this is the final event
                is_final = False
                if hasattr(event, "final") and event.final:
                    is_final = True

                if is_final:
                    break
        finally:
            # Clean up the subscription when done
            async with self.subscriber_lock:
                if task_id in self.task_sse_subscribers:
                    try:
                        self.task_sse_subscribers[task_id].remove(event_queue)
                        # Remove the task from the dict if no more subscribers
                        if not self.task_sse_subscribers[task_id]:
                            del self.task_sse_subscribers[task_id]
                    except ValueError:
                        pass  # Queue might have been removed already
