"""
Routes for the A2A (Agent-to-Agent) protocol.

This module implements the standard A2A routes according to the specification.
"""

import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from src.config.database import get_db
from src.services import agent_service
from src.services import (
    RedisCacheService,
    AgentRunnerAdapter,
    StreamingServiceAdapter,
    create_agent_card_from_agent,
)
from src.services.a2a_task_manager_service import A2ATaskManager
from src.services.a2a_server_service import A2AServer
from src.services.agent_runner import run_agent
from src.services.service_providers import (
    session_service,
    artifacts_service,
    memory_service,
)
from src.services.push_notification_service import push_notification_service
from src.services.push_notification_auth_service import push_notification_auth
from src.services.streaming_service import StreamingService

logger = logging.getLogger(__name__)

# Create router with prefix /a2a according to the standard protocol
router = APIRouter(
    prefix="/a2a",
    tags=["a2a"],
    responses={
        404: {"description": "Not found"},
        400: {"description": "Bad request"},
        401: {"description": "Unauthorized"},
        500: {"description": "Internal server error"},
    },
)

# Singleton instances for shared resources
streaming_service = StreamingService()
redis_cache_service = RedisCacheService()
streaming_adapter = StreamingServiceAdapter(streaming_service)

# Cache dictionary para manter instâncias de A2ATaskManager por agente
# Isso evita criar novas instâncias a cada request
_task_manager_cache = {}
_agent_runner_cache = {}


def get_agent_runner_adapter(db=None, reuse=True, agent_id=None):
    """
    Get or create an agent runner adapter.

    Args:
        db: Database session
        reuse: Whether to reuse an existing instance
        agent_id: Agent ID to use as cache key

    Returns:
        Agent runner adapter instance
    """
    cache_key = str(agent_id) if agent_id else "default"
    logger.info(
        f"[DEBUG] get_agent_runner_adapter chamado para agent_id={agent_id}, reuse={reuse}, cache_key={cache_key}"
    )

    if reuse and cache_key in _agent_runner_cache:
        adapter = _agent_runner_cache[cache_key]
        logger.info(
            f"[DEBUG] Reutilizando agent_runner_adapter existente para {cache_key}"
        )
        # Atualizar a sessão DB se fornecida
        if db is not None:
            adapter.db = db
        return adapter

    logger.info(
        f"[IMPORTANTE] Criando NOVA instância de AgentRunnerAdapter para {cache_key}"
    )
    adapter = AgentRunnerAdapter(
        agent_runner_func=run_agent,
        session_service=session_service,
        artifacts_service=artifacts_service,
        memory_service=memory_service,
        db=db,
    )

    if reuse:
        logger.info(f"[DEBUG] Armazenando nova instância no cache para {cache_key}")
        _agent_runner_cache[cache_key] = adapter

    return adapter


def get_task_manager(agent_id, db=None, reuse=True, operation_type="query"):
    cache_key = str(agent_id)

    # Para operações de consulta, NUNCA crie um agent_runner
    if operation_type == "query":
        if cache_key in _task_manager_cache:
            # Reutilize existente
            task_manager = _task_manager_cache[cache_key]
            task_manager.db = db
            return task_manager

        # Se não existe, crie um task_manager SEM agent_runner para consultas
        return A2ATaskManager(
            redis_cache=redis_cache_service,
            agent_runner=None,  # Sem agent_runner para consultas!
            streaming_service=streaming_adapter,
            push_notification_service=push_notification_service,
            db=db,
        )

    # Para operações de execução, use o fluxo normal
    if reuse and cache_key in _task_manager_cache:
        # Atualize o db
        task_manager = _task_manager_cache[cache_key]
        task_manager.db = db
        return task_manager

    # Create new
    agent_runner_adapter = get_agent_runner_adapter(
        db=db, reuse=reuse, agent_id=agent_id
    )
    task_manager = A2ATaskManager(
        redis_cache=redis_cache_service,
        agent_runner=agent_runner_adapter,
        streaming_service=streaming_adapter,
        push_notification_service=push_notification_service,
        db=db,
    )
    _task_manager_cache[cache_key] = task_manager
    return task_manager


@router.post("/{agent_id}")
async def process_a2a_request(
    agent_id: uuid.UUID,
    request: Request,
    x_api_key: str = Header(None, alias="x-api-key"),
    db: Session = Depends(get_db),
):
    """
    Main endpoint for processing JSON-RPC requests of the A2A protocol.

    This endpoint processes all JSON-RPC methods of the A2A protocol, including:
    - tasks/send: Sending tasks
    - tasks/sendSubscribe: Sending tasks with streaming
    - tasks/get: Querying task status
    - tasks/cancel: Cancelling tasks
    - tasks/pushNotification/set: Setting push notifications
    - tasks/pushNotification/get: Querying push notification configurations
    - tasks/resubscribe: Resubscribing to receive task updates

    Args:
        agent_id: Agent ID
        request: HTTP request with JSON-RPC payload
        x_api_key: API key for authentication
        db: Database session

    Returns:
        JSON-RPC response or streaming (SSE) depending on the method
    """
    try:
        # Detailed request log
        logger.info(f"Request received for A2A agent {agent_id}")
        logger.info(f"Headers: {dict(request.headers)}")

        try:
            body = await request.json()
            method = body.get("method", "unknown")
            logger.info(f"[IMPORTANTE] Método solicitado: {method}")
            logger.info(f"Request body: {body}")

            # Determinar se é uma solicitação de consulta (get_task) ou execução (send_task)
            is_query_request = method in [
                "tasks/get",
                "tasks/cancel",
                "tasks/pushNotification/get",
                "tasks/resubscribe",
            ]
            # Para consultas, reutilizamos os componentes; para execuções,
            # criamos novos para garantir estado limpo
            reuse_components = is_query_request
            logger.info(
                f"[IMPORTANTE] Is query request: {is_query_request}, Reuse components: {reuse_components}"
            )

        except Exception as e:
            logger.error(f"Error reading request body: {e}")
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}",
                        "data": None,
                    },
                },
            )

        # Verify if the agent exists
        agent = agent_service.get_agent(db, agent_id)
        if agent is None:
            logger.warning(f"Agent not found: {agent_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": 404, "message": "Agent not found", "data": None},
                },
            )

        # Verify API key
        agent_config = agent.config
        logger.info(f"Received API Key: {x_api_key}")
        logger.info(f"Expected API Key: {agent_config.get('api_key')}")

        if x_api_key and agent_config.get("api_key") != x_api_key:
            logger.warning(f"Invalid API Key for agent {agent_id}")
            return JSONResponse(
                status_code=401,
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": 401, "message": "Invalid API key", "data": None},
                },
            )

        # Obter o task manager para este agente (reutilizando se possível)
        a2a_task_manager = get_task_manager(
            agent_id,
            db=db,
            reuse=reuse_components,
            operation_type="query" if is_query_request else "execution",
        )
        a2a_server = A2AServer(task_manager=a2a_task_manager)

        # Configure agent_card for the A2A server
        logger.info("Configuring agent_card for A2A server")
        agent_card = create_agent_card_from_agent(agent, db)
        a2a_server.agent_card = agent_card

        # Verify JSON-RPC format
        if not body.get("jsonrpc") or body.get("jsonrpc") != "2.0":
            logger.error(f"Invalid JSON-RPC format: {body.get('jsonrpc')}")
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request: jsonrpc must be '2.0'",
                        "data": None,
                    },
                },
            )

        # Verify the method
        if not body.get("method"):
            logger.error("Method not specified in request")
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request: method is required",
                        "data": None,
                    },
                },
            )

        logger.info(f"Processing method: {body.get('method')}")

        # Process the request with the A2A server
        logger.info("Sending request to A2A server")

        # Pass the agent_id and db directly to the process_request method
        return await a2a_server.process_request(request, agent_id=str(agent_id), db=db)

    except Exception as e:
        logger.error(f"Error processing A2A request: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": "Internal server error",
                    "data": {"detail": str(e)},
                },
            },
        )


@router.get("/{agent_id}/.well-known/agent.json")
async def get_agent_card(
    agent_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Endpoint to get the Agent Card in the .well-known format of the A2A protocol.

    This endpoint returns the agent information in the standard A2A format,
    including capabilities, authentication information, and skills.

    Args:
        agent_id: Agent ID
        request: HTTP request
        db: Database session

    Returns:
        Agent Card in JSON format
    """
    try:
        agent = agent_service.get_agent(db, agent_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
            )

        agent_card = create_agent_card_from_agent(agent, db)

        # Obter o task manager para este agente (reutilizando se possível)
        a2a_task_manager = get_task_manager(agent_id, db=db, reuse=True)
        a2a_server = A2AServer(task_manager=a2a_task_manager)

        # Configure the A2A server with the agent card
        a2a_server.agent_card = agent_card

        # Use the A2A server to deliver the agent card, ensuring protocol compatibility
        return await a2a_server.get_agent_card(request, db=db)

    except Exception as e:
        logger.error(f"Error generating agent card: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating agent card",
        )


@router.get("/{agent_id}/.well-known/jwks.json")
async def get_jwks(
    agent_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Endpoint to get the public JWKS keys for verifying the authenticity
    of push notifications.

    Clients can use these keys to verify the authenticity of received notifications.

    Args:
        agent_id: Agent ID
        request: HTTP request
        db: Database session

    Returns:
        JSON with the public keys in JWKS format
    """
    try:
        # Verify if the agent exists
        agent = agent_service.get_agent(db, agent_id)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
            )

        # Return the public keys
        return push_notification_auth.handle_jwks_endpoint(request)

    except Exception as e:
        logger.error(f"Error obtaining JWKS: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obtaining JWKS",
        )
