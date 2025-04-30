# Implementação do Servidor A2A (Agent-to-Agent)

## Visão Geral

Este documento descreve o plano de implementação para integrar o servidor A2A (Agent-to-Agent) no sistema existente. A implementação seguirá os exemplos fornecidos nos arquivos de referência, adaptando-os à estrutura atual do projeto.

## Componentes a Serem Implementados

### 1. Servidor A2A

Implementação da classe `A2AServer` como serviço para gerenciar requisições JSON-RPC compatíveis com o protocolo A2A.

### 2. Gerenciador de Tarefas

Implementação do `TaskManager` como serviço para gerenciar o ciclo de vida das tarefas do agente.

### 3. Adaptadores para Integração

Criação de adaptadores para integrar o servidor A2A com os serviços existentes, como o streaming_service e push_notification_service.

## Rotas e Endpoints A2A

O protocolo A2A requer a implementação das seguintes rotas JSON-RPC:

### 1. `POST /a2a/{agent_id}`

Endpoint principal que processa todas as solicitações JSON-RPC para um agente específico.

### 2. `GET /a2a/{agent_id}/.well-known/agent.json`

Retorna o Agent Card contendo as informações do agente.

### Métodos JSON-RPC implementados:

1. **tasks/send** - Envia uma nova tarefa para o agente.

   - Parâmetros: `id`, `sessionId`, `message`, `acceptedOutputModes` (opcional), `pushNotification` (opcional)
   - Retorna: Status da tarefa, artefatos gerados e histórico

2. **tasks/sendSubscribe** - Envia uma tarefa e assina para receber atualizações via streaming (SSE).

   - Parâmetros: Mesmos do `tasks/send`
   - Retorna: Stream de eventos SSE com atualizações de status e artefatos

3. **tasks/get** - Obtém o status atual de uma tarefa.

   - Parâmetros: `id`, `historyLength` (opcional)
   - Retorna: Status atual da tarefa, artefatos e histórico

4. **tasks/cancel** - Tenta cancelar uma tarefa em execução.

   - Parâmetros: `id`
   - Retorna: Status atualizado da tarefa

5. **tasks/pushNotification/set** - Configura notificações push para uma tarefa.

   - Parâmetros: `id`, `pushNotificationConfig` (URL e autenticação)
   - Retorna: Configuração de notificação atualizada

6. **tasks/pushNotification/get** - Obtém a configuração de notificações push de uma tarefa.

   - Parâmetros: `id`
   - Retorna: Configuração de notificação atual

7. **tasks/resubscribe** - Reassina para receber eventos de uma tarefa existente.
   - Parâmetros: `id`
   - Retorna: Stream de eventos SSE

## Streaming e Push Notifications

### Streaming (SSE)

O streaming será implementado usando Server-Sent Events (SSE) para enviar atualizações em tempo real aos clientes.

#### Integração com streaming_service.py existente

O serviço atual `StreamingService` já implementa funcionalidades de streaming SSE. Iremos expandir e adaptar:

```python
# Exemplo de integração com o streaming_service.py existente
async def send_task_streaming(request: SendTaskStreamingRequest) -> AsyncIterable[SendTaskStreamingResponse]:
    stream_service = StreamingService()

    async for event in stream_service.send_task_streaming(
        agent_id=request.params.metadata.get("agent_id"),
        api_key=api_key,
        message=request.params.message.parts[0].text,
        session_id=request.params.sessionId,
        db=db
    ):
        # Converter formato de evento SSE para formato A2A
        yield SendTaskStreamingResponse(
            id=request.id,
            result=convert_to_a2a_event_format(event)
        )
```

### Push Notifications

O sistema de notificações push permitirá que o agente envie atualizações para URLs de callback configuradas pelos clientes.

#### Integração com push_notification_service.py existente

O serviço atual `PushNotificationService` já implementa o envio de notificações. Iremos adaptar:

```python
# Exemplo de integração com o push_notification_service.py existente
async def send_push_notification(task_id, state, message=None):
    notification_config = await get_push_notification_config(task_id)
    if notification_config:
        await push_notification_service.send_notification(
            url=notification_config.url,
            task_id=task_id,
            state=state,
            message=message,
            headers=notification_config.headers
        )
```

#### Autenticação de Push Notifications

Implementaremos autenticação segura para as notificações push baseada em JWT usando o `PushNotificationAuth`:

```python
# Exemplo de como configurar autenticação nas notificações
push_auth = PushNotificationSenderAuth()
push_auth.generate_jwk()

# Incluir rota para obter as chaves públicas
@router.get("/{agent_id}/.well-known/jwks.json")
async def get_jwks(agent_id: str):
    return push_auth.handle_jwks_endpoint(request)

# Integrar autenticação ao enviar notificações
async def send_authenticated_push_notification(url, data):
    await push_auth.send_push_notification(url, data)
```

## Estratégia de Armazenamento de Dados

### Uso de Redis para Dados Temporários

Utilizaremos Redis para armazenamento e gerenciamento dos dados temporários das tarefas A2A, substituindo o cache em memória do exemplo original:

```python
from src.services.redis_cache_service import RedisCacheService

class RedisCache:
    def __init__(self, redis_service: RedisCacheService):
        self.redis = redis_service

    # Métodos para gerenciamento de tarefas
    async def get_task(self, task_id: str) -> dict:
        """Recupera uma tarefa pelo ID."""
        return self.redis.get(f"task:{task_id}")

    async def save_task(self, task_id: str, task_data: dict, ttl: int = 3600) -> None:
        """Salva uma tarefa com TTL configurável."""
        self.redis.set(f"task:{task_id}", task_data, ttl=ttl)

    async def update_task_status(self, task_id: str, status: dict) -> bool:
        """Atualiza o status de uma tarefa."""
        task_data = await self.get_task(task_id)
        if not task_data:
            return False
        task_data["status"] = status
        await self.save_task(task_id, task_data)
        return True

    # Métodos para histórico de tarefas
    async def append_to_history(self, task_id: str, message: dict) -> bool:
        """Adiciona uma mensagem ao histórico da tarefa."""
        task_data = await self.get_task(task_id)
        if not task_data:
            return False

        if "history" not in task_data:
            task_data["history"] = []

        task_data["history"].append(message)
        await self.save_task(task_id, task_data)
        return True

    # Métodos para notificações push
    async def save_push_notification_config(self, task_id: str, config: dict) -> None:
        """Salva a configuração de notificação push para uma tarefa."""
        self.redis.set(f"push_notification:{task_id}", config, ttl=3600)

    async def get_push_notification_config(self, task_id: str) -> dict:
        """Recupera a configuração de notificação push de uma tarefa."""
        return self.redis.get(f"push_notification:{task_id}")

    # Métodos para SSE (Server-Sent Events)
    async def save_sse_client(self, task_id: str, client_id: str) -> None:
        """Registra um cliente SSE para uma tarefa."""
        self.redis.set_hash(f"sse_clients:{task_id}", client_id, "active")

    async def get_sse_clients(self, task_id: str) -> list:
        """Recupera todos os clientes SSE registrados para uma tarefa."""
        return self.redis.get_all_hash(f"sse_clients:{task_id}")

    async def remove_sse_client(self, task_id: str, client_id: str) -> None:
        """Remove um cliente SSE do registro."""
        self.redis.delete_hash(f"sse_clients:{task_id}", client_id)
```

O serviço Redis será configurado com TTL (time-to-live) para garantir a limpeza automática de dados temporários:

```python
# Configuração de TTL para diferentes tipos de dados
TASK_TTL = 3600  # 1 hora para tarefas
HISTORY_TTL = 86400  # 24 horas para histórico
PUSH_NOTIFICATION_TTL = 3600  # 1 hora para configurações de notificação
SSE_CLIENT_TTL = 300  # 5 minutos para clientes SSE
```

### Modelos Existentes e Redis

O sistema continuará utilizando os modelos SQLAlchemy existentes para dados permanentes:

- **Agent**: Dados do agente e configurações
- **Session**: Sessões persistentes
- **MCPServer**: Configurações de servidores de ferramentas

Para dados temporários (tarefas A2A, histórico, streaming), utilizaremos Redis que oferece:

1. **Performance**: Operações em memória com persistência opcional
2. **TTL**: Expiração automática de dados temporários
3. **Estruturas de dados**: Suporte a strings, hashes, listas para diferentes necessidades
4. **Pub/Sub**: Mecanismo para notificações em tempo real
5. **Escalabilidade**: Melhor suporte a múltiplas instâncias do que cache em memória

### Implementação do TaskManager com Redis

O `A2ATaskManager` implementará a mesma interface que o `TaskManager` do exemplo, mas utilizando Redis:

```python
class A2ATaskManager:
    """
    Gerenciador de tarefas A2A usando Redis para armazenamento.
    Implementa a interface do protocolo A2A para gerenciamento do ciclo de vida das tarefas.
    """

    def __init__(
        self,
        redis_cache: RedisCacheService,
        session_service=None,
        artifacts_service=None,
        memory_service=None,
        push_notification_service=None
    ):
        self.redis_cache = redis_cache
        self.session_service = session_service
        self.artifacts_service = artifacts_service
        self.memory_service = memory_service
        self.push_notification_service = push_notification_service
        self.lock = asyncio.Lock()
        self.subscriber_lock = asyncio.Lock()
        self.task_sse_subscribers = {}

    async def on_get_task(self, request: GetTaskRequest) -> GetTaskResponse:
        """
        Obtém o status atual de uma tarefa.

        Args:
            request: Requisição JSON-RPC para obter dados da tarefa

        Returns:
            Resposta com dados da tarefa ou erro
        """
        logger.info(f"Getting task {request.params.id}")
        task_query_params = request.params

        task_data = self.redis_cache.get(f"task:{task_query_params.id}")
        if not task_data:
            return GetTaskResponse(id=request.id, error=TaskNotFoundError())

        # Processar histórico conforme solicitado
        if task_query_params.historyLength and task_data.get("history"):
            task_data["history"] = task_data["history"][-task_query_params.historyLength:]

        return GetTaskResponse(id=request.id, result=task_data)
```

## Implementação do A2A Server Service

O serviço `A2AServer` processará as requisições JSON-RPC conforme o protocolo A2A:

```python
class A2AServer:
    """
    Servidor A2A que implementa o protocolo JSON-RPC para processamento de tarefas de agentes.
    """

    def __init__(
        self,
        endpoint: str = "/",
        agent_card = None,
        task_manager = None,
        streaming_service = None,
    ):
        self.endpoint = endpoint
        self.agent_card = agent_card
        self.task_manager = task_manager
        self.streaming_service = streaming_service

    async def _process_request(self, request: Request):
        """
        Processa uma requisição JSON-RPC do protocolo A2A.

        Args:
            request: Requisição HTTP

        Returns:
            Resposta JSON-RPC ou stream de eventos
        """
        try:
            body = await request.json()
            json_rpc_request = A2ARequest.validate_python(body)

            # Delegar para o handler apropriado com base no tipo de requisição
            if isinstance(json_rpc_request, GetTaskRequest):
                result = await self.task_manager.on_get_task(json_rpc_request)
            elif isinstance(json_rpc_request, SendTaskRequest):
                result = await self.task_manager.on_send_task(json_rpc_request)
            elif isinstance(json_rpc_request, SendTaskStreamingRequest):
                result = await self.task_manager.on_send_task_subscribe(json_rpc_request)
            elif isinstance(json_rpc_request, CancelTaskRequest):
                result = await self.task_manager.on_cancel_task(json_rpc_request)
            elif isinstance(json_rpc_request, SetTaskPushNotificationRequest):
                result = await self.task_manager.on_set_task_push_notification(json_rpc_request)
            elif isinstance(json_rpc_request, GetTaskPushNotificationRequest):
                result = await self.task_manager.on_get_task_push_notification(json_rpc_request)
            elif isinstance(json_rpc_request, TaskResubscriptionRequest):
                result = await self.task_manager.on_resubscribe_to_task(json_rpc_request)
            else:
                logger.warning(f"Unexpected request type: {type(json_rpc_request)}")
                raise ValueError(f"Unexpected request type: {type(json_rpc_request)}")

            return self._create_response(result)

        except Exception as e:
            return self._handle_exception(e)
```

## Implementação da Autenticação para Push Notifications

Implementaremos autenticação JWT para notificações push, seguindo o exemplo:

```python
class PushNotificationAuth:
    def __init__(self):
        self.public_keys = []
        self.private_key_jwk = None

    def generate_jwk(self):
        key = jwk.JWK.generate(kty='RSA', size=2048, kid=str(uuid.uuid4()), use="sig")
        self.public_keys.append(key.export_public(as_dict=True))
        self.private_key_jwk = PyJWK.from_json(key.export_private())

    def handle_jwks_endpoint(self, request: Request):
        """Retorna as chaves públicas para clientes."""
        return JSONResponse({"keys": self.public_keys})

    async def send_authenticated_push_notification(self, url: str, data: dict):
        """Envia notificação push assinada com JWT."""
        jwt_token = self._generate_jwt(data)
        headers = {'Authorization': f"Bearer {jwt_token}"}
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.post(url, json=data, headers=headers)
                response.raise_for_status()
                logger.info(f"Push-notification sent to URL: {url}")
            except Exception as e:
                logger.warning(f"Error sending push-notification to URL {url}: {e}")
```

## Revisão das Rotas A2A

As rotas A2A serão implementadas em `src/api/a2a_routes.py`, utilizando a lógica de AgentCard do código existente:

```python
@router.post("/{agent_id}")
async def process_a2a_request(
    agent_id: str,
    request: Request,
    x_api_key: str = Header(None, alias="x-api-key"),
    db: Session = Depends(get_db),
):
    """
    Endpoint que processa requisições JSON-RPC do protocolo A2A.
    """
    # Validar agente e API key
    agent = get_agent(db, agent_id)
    if not agent:
        return JSONResponse(
            status_code=404,
            content={"detail": "Agente não encontrado"}
        )

    if agent.config.get("api_key") != x_api_key:
        return JSONResponse(
            status_code=401,
            content={"detail": "Chave API inválida"}
        )

    # Criar Agent Card para o agente (reutilizando lógica existente)
    agent_card = create_agent_card_from_agent(agent, db)

    # Configurar o servidor A2A para este agente
    a2a_server.agent_card = agent_card

    # Processar a requisição A2A
    return await a2a_server._process_request(request)
```

## Arquivos a Serem Criados/Atualizados

### Novos Arquivos

1. `src/schemas/a2a.py` - Modelos Pydantic para o protocolo A2A
2. `src/services/redis_cache_service.py` - Serviço de cache Redis
3. `src/config/redis.py` - Configuração do cliente Redis
4. `src/utils/a2a_utils.py` - Utilitários para o protocolo A2A
5. `src/services/a2a_task_manager_service.py` - Gerenciador de tarefas A2A
6. `src/services/a2a_server_service.py` - Servidor A2A
7. `src/services/push_notification_auth_service.py` - Autenticação para push notifications
8. `src/api/a2a_routes.py` - Rotas para o protocolo A2A

### Arquivos a Serem Atualizados

1. `src/main.py` - Registrar novas rotas A2A
2. `pyproject.toml` - Adicionar dependências (Redis, jwcrypto, etc.)

## Plano de Implementação

### Fase 1: Criação dos Esquemas

1. Criar arquivo `src/schemas/a2a.py` com os modelos Pydantic baseados no arquivo `common/types.py`
2. Adaptar os tipos para a estrutura do projeto e adicionar suporte para streaming e push notifications

### Fase 2: Implementação do Serviço de Cache Redis

1. Criar arquivo `src/config/redis.py` para configuração do cliente Redis
2. Criar arquivo `src/services/redis_cache_service.py` para gerenciamento de cache

### Fase 3: Implementação de Utilitários

1. Criar arquivo `src/utils/a2a_utils.py` com funções utilitárias baseadas em `common/server/utils.py`
2. Adaptar o `PushNotificationAuth` para uso no contexto A2A

### Fase 4: Implementação do Gerenciador de Tarefas

1. Criar arquivo `src/services/a2a_task_manager_service.py` com a implementação do `A2ATaskManager`
2. Integrar com serviços existentes:
   - agent_runner.py para execução de agentes
   - streaming_service.py para streaming SSE
   - push_notification_service.py para push notifications
   - redis_cache_service.py para cache de tarefas

### Fase 5: Implementação do Servidor A2A

1. Criar arquivo `src/services/a2a_server_service.py` com a implementação do `A2AServer`
2. Implementar processamento de requisições JSON-RPC para todas as operações A2A

### Fase 6: Integração

1. Criar arquivo `src/api/a2a_routes.py` com rotas para o protocolo A2A
2. Registrar as rotas no aplicativo FastAPI principal
3. Assegurar que todas as operações A2A funcionem corretamente, incluindo streaming e push notifications

## Adaptações Necessárias

1. **Esquemas**: Adaptar os modelos do protocolo A2A para usar os esquemas Pydantic existentes quando possível
2. **Autenticação**: Integrar com o sistema de autenticação existente usando API keys
3. **Streaming**: Adaptar o `StreamingService` existente para o formato de eventos A2A
4. **Push Notifications**: Integrar o `PushNotificationService` existente e adicionar suporte a autenticação JWT
5. **Cache**: Utilizar Redis para armazenamento temporário de tarefas e eventos
6. **Execução de Agentes**: Reutilizar o serviço existente `agent_runner.py` para execução

## Próximos Passos

1. Configurar dependências do Redis no projeto
2. Implementar os esquemas em `src/schemas/a2a.py`
3. Implementar o serviço de cache Redis
4. Implementar as funções utilitárias em `src/utils/a2a_utils.py`
5. Implementar o gerenciador de tarefas em `src/services/a2a_task_manager_service.py`
6. Implementar o servidor A2A em `src/services/a2a_server_service.py`
7. Implementar as rotas em `src/api/a2a_routes.py`
8. Registrar as rotas no aplicativo principal `src/main.py`
9. Testar a implementação com casos de uso completos, incluindo streaming e push notifications
