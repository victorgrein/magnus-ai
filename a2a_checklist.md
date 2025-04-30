# Checklist de Implementação do Protocolo A2A com Redis

## 1. Configuração Inicial

- [ ] **Configurar dependências no arquivo pyproject.toml**

  - Adicionar Redis e dependências relacionadas:
    ```
    redis = "^5.3.0"
    sse-starlette = "^2.3.3"
    jwcrypto = "^1.5.6"
    pyjwt = {extras = ["crypto"], version = "^2.10.1"}
    ```

- [ ] **Configurar variáveis de ambiente para Redis**

  - Adicionar em `.env.example` e `.env`:
    ```
    REDIS_HOST=localhost
    REDIS_PORT=6379
    REDIS_PASSWORD=
    REDIS_DB=0
    REDIS_SSL=false
    REDIS_KEY_PREFIX=a2a:
    REDIS_TTL=3600
    ```

- [ ] **Configurar Redis no docker-compose.yml**
  - Adicionar serviço Redis com portas e volumes apropriados
  - Configurar segurança básica (senha, se necessário)

## 2. Implementação de Modelos e Schemas

- [ ] **Criar schemas A2A em `src/schemas/a2a.py`**

  - Implementar tipos conforme `docs/A2A/samples/python/common/types.py`:
    - Enums (TaskState, etc.)
    - Classes de mensagens (TextPart, FilePart, etc.)
    - Classes de tarefas (Task, TaskStatus, etc.)
    - Estruturas JSON-RPC
    - Tipos de erros

- [ ] **Implementar validadores de modelo**
  - Validadores para conteúdos de arquivo
  - Validadores para formatos de mensagem
  - Conversores de formato para compatibilidade com o protocolo

## 3. Implementação do Cache Redis

- [ ] **Criar configuração Redis em `src/config/redis.py`**

  - Implementar função de conexão com pool
  - Configurar opções de segurança (SSL, autenticação)
  - Configurar TTL padrão para diferentes tipos de dados

- [ ] **Criar serviço de cache Redis em `src/services/redis_cache_service.py`**

  - Implementar métodos do exemplo com suporte a Redis:
    ```python
    class RedisCache:
        async def get_task(self, task_id: str) -> dict
        async def save_task(self, task_id: str, task_data: dict, ttl: int = 3600) -> None
        async def update_task_status(self, task_id: str, status: dict) -> bool
        async def append_to_history(self, task_id: str, message: dict) -> bool
        async def save_push_notification_config(self, task_id: str, config: dict) -> None
        async def get_push_notification_config(self, task_id: str) -> dict
        async def save_sse_client(self, task_id: str, client_id: str) -> None
        async def get_sse_clients(self, task_id: str) -> list
        async def remove_sse_client(self, task_id: str, client_id: str) -> None
    ```

- [ ] **Implementar funcionalidades para gerenciamento de conexões**
  - Reconexão automática
  - Fallback para cache em memória em caso de falha
  - Métricas de desempenho

## 4. Serviços A2A

- [ ] **Implementar utilitários A2A em `src/utils/a2a_utils.py`**

  - Implementar funções conforme `docs/A2A/samples/python/common/server/utils.py`:
    ```python
    def are_modalities_compatible(server_output_modes, client_output_modes)
    def new_incompatible_types_error(request_id)
    def new_not_implemented_error(request_id)
    ```

- [ ] **Implementar `A2ATaskManager` em `src/services/a2a_task_manager_service.py`**

  - Seguir a interface do `TaskManager` do exemplo
  - Implementar todos os métodos abstratos:
    ```python
    async def on_get_task(self, request: GetTaskRequest) -> GetTaskResponse
    async def on_cancel_task(self, request: CancelTaskRequest) -> CancelTaskResponse
    async def on_send_task(self, request: SendTaskRequest) -> SendTaskResponse
    async def on_send_task_subscribe(self, request) -> Union[AsyncIterable, JSONRPCResponse]
    async def on_set_task_push_notification(self, request) -> SetTaskPushNotificationResponse
    async def on_get_task_push_notification(self, request) -> GetTaskPushNotificationResponse
    async def on_resubscribe_to_task(self, request) -> Union[AsyncIterable, JSONRPCResponse]
    ```
  - Utilizar Redis para persistência de dados de tarefa

- [ ] **Implementar `A2AServer` em `src/services/a2a_server_service.py`**

  - Processar requisições JSON-RPC conforme `docs/A2A/samples/python/common/server/server.py`:
    ```python
    async def _process_request(self, request: Request)
    def _handle_exception(self, e: Exception) -> JSONResponse
    def _create_response(self, result: Any) -> Union[JSONResponse, EventSourceResponse]
    ```

- [ ] **Integrar com agent_runner.py existente**

  - Adaptar `run_agent` para uso no contexto de tarefas A2A
  - Implementar mapeamento entre formatos de mensagem

- [ ] **Integrar com streaming_service.py existente**
  - Adaptar para formato de eventos compatível com A2A
  - Implementar suporte a streaming de múltiplos tipos de eventos

## 5. Autenticação e Push Notifications

- [ ] **Implementar `PushNotificationAuth` em `src/services/push_notification_auth_service.py`**

  - Seguir o exemplo em `docs/A2A/samples/python/common/utils/push_notification_auth.py`
  - Implementar:
    ```python
    def generate_jwk(self)
    def handle_jwks_endpoint(self, request: Request)
    async def send_authenticated_push_notification(self, url: str, data: dict)
    ```

- [ ] **Implementar verificação de URL de notificação**

  - Seguir método `verify_push_notification_url` do exemplo
  - Implementar validação de token para verificação

- [ ] **Implementar armazenamento seguro de chaves**
  - Armazenar chaves privadas de forma segura
  - Rotação periódica de chaves
  - Gerenciamento do ciclo de vida das chaves

## 6. Rotas A2A

- [ ] **Implementar rotas em `src/api/a2a_routes.py`**

  - Criar endpoint principal para processamento de requisições JSON-RPC:

    ```python
    @router.post("/{agent_id}")
    async def process_a2a_request(agent_id: str, request: Request, x_api_key: str = Header(None))
    ```

  - Implementar endpoint do Agent Card reutilizando lógica existente:

    ```python
    @router.get("/{agent_id}/.well-known/agent.json")
    async def get_agent_card(agent_id: str, db: Session = Depends(get_db))
    ```

  - Implementar endpoint JWKS para autenticação de push notifications:
    ```python
    @router.get("/{agent_id}/.well-known/jwks.json")
    async def get_jwks(agent_id: str, db: Session = Depends(get_db))
    ```

- [ ] **Registrar rotas A2A no aplicativo principal**
  - Adicionar importação e inclusão em `src/main.py`:
    ```python
    app.include_router(a2a_routes.router, prefix="/api/v1")
    ```

## 7. Testes

- [ ] **Criar testes unitários para schemas A2A**

  - Testar validadores
  - Testar conversões de formato
  - Testar compatibilidade de modalidades

- [ ] **Criar testes unitários para cache Redis**

  - Testar todas as operações CRUD
  - Testar expiração de dados
  - Testar comportamento com falhas de conexão

- [ ] **Criar testes unitários para gerenciador de tarefas**

  - Testar ciclo de vida da tarefa
  - Testar cancelamento de tarefas
  - Testar notificações push

- [ ] **Criar testes de integração para endpoints A2A**
  - Testar requisições completas
  - Testar streaming
  - Testar cenários de erro

## 8. Segurança

- [ ] **Implementar validação de API key**

  - Verificar API key para todas as requisições
  - Implementar rate limiting por agente/cliente

- [ ] **Configurar segurança no Redis**

  - Ativar autenticação e SSL em produção
  - Definir políticas de retenção de dados
  - Implementar backup e recuperação

- [ ] **Configurar segurança para push notifications**
  - Implementar assinatura JWT
  - Validar URLs de callback
  - Implementar retry com backoff para falhas

## 9. Monitoramento e Métricas

- [ ] **Implementar métricas de Redis**

  - Taxa de acertos/erros do cache
  - Tempo de resposta
  - Uso de memória

- [ ] **Implementar métricas de tarefas A2A**

  - Número de tarefas por estado
  - Tempo médio de processamento
  - Taxa de erros

- [ ] **Configurar logging apropriado**
  - Registrar eventos importantes
  - Mascarar dados sensíveis
  - Implementar níveis de log configuráveis

## 10. Documentação

- [ ] **Documentar API A2A**

  - Descrever endpoints e formatos
  - Fornecer exemplos de uso
  - Documentar erros e soluções

- [ ] **Documentar integração com Redis**

  - Descrever configuração
  - Explicar estratégia de cache
  - Documentar TTLs e políticas de expiração

- [ ] **Criar exemplos de clients**
  - Implementar exemplos de uso em Python
  - Documentar fluxos comuns
  - Fornecer snippets para linguagens populares
