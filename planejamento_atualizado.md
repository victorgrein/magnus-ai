# Planejamento de Implementação - A2A Streaming (Atualizado)

## 1. Visão Geral

Implementar suporte a Server-Sent Events (SSE) para streaming de atualizações de tarefas em tempo real, seguindo a especificação oficial do A2A.

## 2. Componentes Necessários

### 2.2 Estrutura de Arquivos

```
src/
├── api/
│   └── agent_routes.py (modificação)
├── schemas/
│   └── streaming.py (novo)
├── services/
│   └── streaming_service.py (novo)
└── utils/
    └── streaming.py (novo)
```

## 3. Implementação

### 3.1 Schemas (Pydantic)

```python
# schemas/streaming.py
- TaskStatusUpdateEvent
  - state: str (working, completed, failed)
  - timestamp: datetime
  - message: Optional[Message]
  - error: Optional[Error]

- TaskArtifactUpdateEvent
  - type: str
  - content: str
  - metadata: Dict[str, Any]

- JSONRPCRequest
  - jsonrpc: str = "2.0"
  - id: str
  - method: str = "tasks/sendSubscribe"
  - params: Dict[str, Any]

- Message
  - role: str
  - parts: List[MessagePart]

- MessagePart
  - type: str
  - text: str
```

### 3.2 Serviço de Streaming

````python
# services/streaming_service.py
- send_task_streaming()
  - Monta payload JSON-RPC conforme especificação:
    ```json
    {
      "jsonrpc": "2.0",
      "id": "<uuid>",
      "method": "tasks/sendSubscribe",
      "params": {
        "id": "<uuid>",
        "sessionId": "<opcional>",
        "message": {
          "role": "user",
          "parts": [{"type": "text", "text": "<mensagem>"}]
        }
      }
    }
    ```
  - Configura headers:
    - Accept: text/event-stream
    - Authorization: x-api-key <SUA_API_KEY>
  - Gerencia conexão SSE
  - Processa eventos em tempo real
````

### 3.3 Rota de Streaming

```python
# api/agent_routes.py
- Nova rota POST /{agent_id}/tasks/sendSubscribe
  - Validação de API key
  - Gerenciamento de sessão
  - Streaming de eventos SSE
  - Tratamento de erros JSON-RPC
```

### 3.4 Utilitários

```python
# utils/streaming.py
- Helpers para SSE
  - Formatação de eventos
  - Tratamento de reconexão
  - Timeout e retry
- Processamento de eventos
  - Parsing de eventos SSE
  - Validação de payloads
- Formatação de respostas
  - Conformidade com JSON-RPC 2.0
```

## 4. Fluxo de Dados

1. Cliente envia requisição JSON-RPC para `/tasks/sendSubscribe`
2. Servidor valida API key e configura sessão
3. Inicia streaming de eventos SSE
4. Envia atualizações em tempo real:
   - TaskStatusUpdateEvent (estado da tarefa)
   - TaskArtifactUpdateEvent (artefatos gerados)
   - Mensagens do histórico

## 5. Exemplo de Uso

```python
async def exemplo_uso():
    agent_id = "uuid-do-agente"
    api_key = "sua-api-key"
    mensagem = "Olá, como posso ajudar?"

    async with httpx.AsyncClient() as client:
        # Configura headers
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"x-api-key {api_key}"
        }

        # Monta payload JSON-RPC
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tasks/sendSubscribe",
            "params": {
                "id": str(uuid.uuid4()),
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": mensagem}]
                }
            }
        }

        # Inicia streaming
        async with connect_sse(client, "POST", f"/agents/{agent_id}/tasks/sendSubscribe",
                             json=payload, headers=headers) as event_source:
            async for event in event_source.aiter_sse():
                if event.event == "message":
                    data = json.loads(event.data)
                    print(f"Evento recebido: {data}")
```

## 6. Considerações de Segurança

- Validação rigorosa de API keys
- Timeout de conexão SSE (30 segundos)
- Tratamento de erros e reconexão automática
- Limites de taxa (rate limiting)
- Validação de payloads JSON-RPC
- Sanitização de inputs

## 7. Testes

- Testes unitários para schemas
- Testes de integração para streaming
- Testes de carga e performance
- Testes de reconexão e resiliência
- Testes de conformidade JSON-RPC

## 8. Documentação

- Atualizar documentação da API
- Adicionar exemplos de uso
- Documentar formatos de eventos
- Guia de troubleshooting
- Referência à especificação A2A

## 9. Próximos Passos

1. Implementar schemas Pydantic conforme especificação
2. Desenvolver serviço de streaming com suporte a JSON-RPC
3. Adicionar rota SSE com validação de payloads
4. Implementar utilitários de streaming
5. Escrever testes de conformidade
6. Atualizar documentação
7. Revisão de código
8. Deploy em ambiente de teste
