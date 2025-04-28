# Evo AI - Plataforma de Agentes de IA

Evo AI é uma plataforma open-source para criação e gerenciamento de agentes de IA, permitindo a integração com diferentes modelos e serviços de IA.

## 🚀 Visão Geral

O Evo AI é uma plataforma que permite:
- Criação e gerenciamento de agentes de IA
- Integração com diferentes modelos de linguagem
- Gerenciamento de clientes e contatos
- Configuração de servidores MCP
- Gerenciamento de ferramentas personalizadas
- Autenticação via API Key

## 🛠️ Tecnologias

- **FastAPI**: Framework web para construção da API
- **SQLAlchemy**: ORM para interação com o banco de dados
- **PostgreSQL**: Banco de dados principal
- **Alembic**: Sistema de migrações
- **Pydantic**: Validação e serialização de dados
- **Uvicorn**: Servidor ASGI
- **Redis**: Cache e gerenciamento de sessões

## 📁 Estrutura do Projeto

```
src/
├── api/          # Endpoints da API
├── core/         # Lógica central do negócio
├── models/       # Modelos de dados
├── schemas/      # Schemas Pydantic para validação
├── utils/        # Utilitários
├── config/       # Configurações
└── services/     # Serviços de negócio
```

## 📋 Requisitos

- Python 3.8+
- PostgreSQL
- Redis
- OpenAI API Key (ou outro provedor de IA)

## 🔧 Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/evo-ai.git
cd evo-ai
```

2. Crie um ambiente virtual:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

5. Execute as migrações:
```bash
make upgrade
```

## 🔐 Autenticação

A API utiliza autenticação via API Key. Para acessar os endpoints, você precisa:

1. Incluir a API Key no header `X-API-Key` de todas as requisições
2. A API Key é gerada automaticamente quando o servidor é iniciado pela primeira vez
3. Você pode encontrar a API Key no arquivo `.env` ou nos logs do servidor

Exemplo de uso com curl:
```bash
curl -X GET "http://localhost:8000/api/clients/" \
     -H "X-API-Key: sua-api-key-aqui"
```

## 🚀 Executando o Projeto

```bash
make run
```

A API estará disponível em `http://localhost:8000`

## 📚 Documentação da API

### Clientes

#### Criar Cliente
```http
POST /clients/
```
Cria um novo cliente.

#### Listar Clientes
```http
GET /clients/
```
Lista todos os clientes com paginação.

#### Buscar Cliente
```http
GET /clients/{client_id}
```
Busca um cliente específico.

#### Atualizar Cliente
```http
PUT /clients/{client_id}
```
Atualiza os dados de um cliente.

#### Remover Cliente
```http
DELETE /clients/{client_id}
```
Remove um cliente.

### Contatos

#### Criar Contato
```http
POST /contacts/
```
Cria um novo contato.

#### Listar Contatos
```http
GET /contacts/{client_id}
```
Lista contatos de um cliente.

#### Buscar Contato
```http
GET /contact/{contact_id}
```
Busca um contato específico.

#### Atualizar Contato
```http
PUT /contact/{contact_id}
```
Atualiza os dados de um contato.

#### Remover Contato
```http
DELETE /contact/{contact_id}
```
Remove um contato.

### Agentes

#### Criar Agente
```http
POST /agents/
```
Cria um novo agente.

#### Listar Agentes
```http
GET /agents/{client_id}
```
Lista agentes de um cliente.

#### Buscar Agente
```http
GET /agent/{agent_id}
```
Busca um agente específico.

#### Atualizar Agente
```http
PUT /agent/{agent_id}
```
Atualiza os dados de um agente.

#### Remover Agente
```http
DELETE /agent/{agent_id}
```
Remove um agente.

### Servidores MCP

#### Criar Servidor MCP
```http
POST /mcp-servers/
```
Cria um novo servidor MCP.

#### Listar Servidores MCP
```http
GET /mcp-servers/
```
Lista todos os servidores MCP.

#### Buscar Servidor MCP
```http
GET /mcp-servers/{server_id}
```
Busca um servidor MCP específico.

#### Atualizar Servidor MCP
```http
PUT /mcp-servers/{server_id}
```
Atualiza os dados de um servidor MCP.

#### Remover Servidor MCP
```http
DELETE /mcp-servers/{server_id}
```
Remove um servidor MCP.

### Ferramentas

#### Criar Ferramenta
```http
POST /tools/
```
Cria uma nova ferramenta.

#### Listar Ferramentas
```http
GET /tools/
```
Lista todas as ferramentas.

#### Buscar Ferramenta
```http
GET /tools/{tool_id}
```
Busca uma ferramenta específica.

#### Atualizar Ferramenta
```http
PUT /tools/{tool_id}
```
Atualiza os dados de uma ferramenta.

#### Remover Ferramenta
```http
DELETE /tools/{tool_id}
```
Remove uma ferramenta.

### Chat

#### Enviar Mensagem
```http
POST /chat
```
Envia uma mensagem para um agente.

## 📝 Documentação Interativa

A documentação interativa da API está disponível em:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 📊 Logs

Os logs são armazenados no diretório `logs/` com o seguinte formato:
- `{nome_do_logger}_{data}.log`

## 🤝 Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request 

## 📄 Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 🙏 Agradecimentos

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Google ADK](https://github.com/google/adk) 