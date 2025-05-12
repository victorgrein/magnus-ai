# Evo AI - AI Agents Platform

Evo AI is an open-source platform for creating and managing AI agents, enabling integration with different AI models and services.

## 🚀 Overview

The Evo AI platform allows:

- Creation and management of AI agents
- Integration with different language models
- Client management
- MCP server configuration
- Custom tools management
- JWT authentication with email verification
- **Agent 2 Agent (A2A) Protocol Support**: Interoperability between AI agents following Google's A2A specification
- **Workflow Agent with LangGraph**: Building complex agent workflows with LangGraph and ReactFlow
- **Secure API Key Management**: Encrypted storage of API keys with Fernet encryption
- **Agent Organization**: Folder structure for organizing agents by categories

## 🤖 Agent Types and Creation

Evo AI supports different types of agents that can be flexibly combined to create complex solutions:

### 1. LLM Agent (Language Model)

Agent based on language models like GPT-4, Claude, etc. Can be configured with tools, MCP servers, and sub-agents.

```json
{
  "client_id": "{{client_id}}",
  "name": "personal_assistant",
  "description": "Specialized personal assistant",
  "type": "llm",
  "model": "gpt-4",
  "api_key_id": "stored-api-key-uuid",
  "folder_id": "folder_id (optional)",
  "instruction": "Detailed instructions for agent behavior",
  "config": {
    "tools": [
      {
        "id": "tool-uuid",
        "envs": {
          "API_KEY": "tool-api-key",
          "ENDPOINT": "http://localhost:8000"
        }
      }
    ],
    "mcp_servers": [
      {
        "id": "server-uuid",
        "envs": {
          "API_KEY": "server-api-key",
          "ENDPOINT": "http://localhost:8001"
        },
        "tools": ["tool_name1", "tool_name2"]
      }
    ],
    "custom_tools": {
      "http_tools": []
    },
    "sub_agents": ["sub-agent-uuid"]
  }
}
```

### 2. A2A Agent (Agent-to-Agent)

Agent that implements Google's A2A protocol for agent interoperability.

```json
{
  "client_id": "{{client_id}}",
  "type": "a2a",
  "agent_card_url": "http://localhost:8001/api/v1/a2a/your-agent/.well-known/agent.json",
  "folder_id": "folder_id (optional)",
  "config": {
    "sub_agents": ["sub-agent-uuid"]
  }
}
```

### 3. Sequential Agent

Executes a sequence of sub-agents in a specific order.

```json
{
  "client_id": "{{client_id}}",
  "name": "processing_flow",
  "type": "sequential",
  "folder_id": "folder_id (optional)",
  "config": {
    "sub_agents": ["agent-uuid-1", "agent-uuid-2", "agent-uuid-3"]
  }
}
```

### 4. Parallel Agent

Executes multiple sub-agents simultaneously.

```json
{
  "client_id": "{{client_id}}",
  "name": "parallel_processing",
  "type": "parallel",
  "folder_id": "folder_id (optional)",
  "config": {
    "sub_agents": ["agent-uuid-1", "agent-uuid-2"]
  }
}
```

### 5. Loop Agent

Executes sub-agents in a loop with a defined maximum number of iterations.

```json
{
  "client_id": "{{client_id}}",
  "name": "loop_processing",
  "type": "loop",
  "folder_id": "folder_id (optional)",
  "config": {
    "sub_agents": ["sub-agent-uuid"],
    "max_iterations": 5
  }
}
```

### 6. Workflow Agent

Executes sub-agents in a custom workflow defined by a graph structure. This agent type uses LangGraph for implementing complex agent workflows with conditional execution paths.

```json
{
  "client_id": "{{client_id}}",
  "name": "workflow_agent",
  "type": "workflow",
  "folder_id": "folder_id (optional)",
  "config": {
    "sub_agents": ["agent-uuid-1", "agent-uuid-2", "agent-uuid-3"],
    "workflow": {
      "nodes": [],
      "edges": []
    }
  }
}
```

The workflow structure is built using ReactFlow in the frontend, allowing visual creation and editing of complex agent workflows with nodes (representing agents or decision points) and edges (representing flow connections).

### Common Characteristics

- All agent types can have sub-agents
- Sub-agents can be of any type
- Agents can be flexibly combined
- Type-specific configurations
- Support for custom tools and MCP servers

### MCP Server Configuration

Agents can be integrated with MCP (Model Control Protocol) servers for distributed processing:

```json
{
  "config": {
    "mcp_servers": [
      {
        "id": "server-uuid",
        "envs": {
          "API_KEY": "server-api-key",
          "ENDPOINT": "http://localhost:8001",
          "MODEL_NAME": "gpt-4",
          "TEMPERATURE": 0.7,
          "MAX_TOKENS": 2000
        },
        "tools": ["tool_name1", "tool_name2"]
      }
    ]
  }
}
```

Available configurations for MCP servers:

- **id**: Unique MCP server identifier
- **envs**: Environment variables for configuration
  - API_KEY: Server authentication key
  - ENDPOINT: MCP server URL
  - MODEL_NAME: Model name to be used
  - TEMPERATURE: Text generation temperature (0.0 to 1.0)
  - MAX_TOKENS: Maximum token limit per request
  - Other server-specific variables
- **tools**: MCP server tool names for agent use

### Agent Composition Examples

Different types of agents can be combined to create complex processing flows:

#### 1. Sequential Processing Pipeline

```json
{
  "client_id": "{{client_id}}",
  "name": "processing_pipeline",
  "type": "sequential",
  "config": {
    "sub_agents": [
      "llm-analysis-agent-uuid", // LLM Agent for initial analysis
      "a2a-translation-agent-uuid", // A2A Agent for translation
      "llm-formatting-agent-uuid" // LLM Agent for final formatting
    ]
  }
}
```

#### 2. Parallel Processing with Aggregation

```json
{
  "client_id": "{{client_id}}",
  "name": "parallel_analysis",
  "type": "sequential",
  "config": {
    "sub_agents": [
      {
        "type": "parallel",
        "config": {
          "sub_agents": [
            "analysis-agent-uuid-1",
            "analysis-agent-uuid-2",
            "analysis-agent-uuid-3"
          ]
        }
      },
      "aggregation-agent-uuid" // Agent for aggregating results
    ]
  }
}
```

#### 3. Multi-Agent Conversation System

```json
{
  "client_id": "{{client_id}}",
  "name": "conversation_system",
  "type": "parallel",
  "config": {
    "sub_agents": [
      {
        "type": "llm",
        "name": "context_agent",
        "model": "gpt-4",
        "instruction": "Maintain conversation context"
      },
      {
        "type": "a2a",
        "agent_card_url": "expert-agent-url"
      },
      {
        "type": "loop",
        "config": {
          "sub_agents": ["memory-agent-uuid"],
          "max_iterations": 1
        }
      }
    ]
  }
}
```

### API Creation

For creating a new agent, use the endpoint:

```http
POST /api/v1/agents
Content-Type: application/json
Authorization: Bearer your-token-jwt

{
    // Configuration of the agent as per the examples above
}
```

## 🛠️ Technologies

- **FastAPI**: Web framework for building the API
- **SQLAlchemy**: ORM for database interaction
- **PostgreSQL**: Main database
- **Alembic**: Migration system
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server
- **Redis**: Cache and session management
- **JWT**: Secure token authentication
- **SendGrid**: Email service for notifications
- **Jinja2**: Template engine for email rendering
- **Bcrypt**: Password hashing and security
- **LangGraph**: Framework for building stateful, multi-agent workflows
- **ReactFlow**: Library for building node-based visual workflows

## 📊 Langfuse Integration (Tracing & Observability)

Evo AI platform natively supports integration with [Langfuse](https://langfuse.com/) for detailed tracing of agent executions, prompts, model responses, and tool calls, using the OpenTelemetry (OTel) standard.

### Why use Langfuse?

- Visual dashboard for agent traces, prompts, and executions
- Detailed analytics for debugging and evaluating LLM apps
- Easy integration with Google ADK and other frameworks

### How it works

- Every agent execution (including streaming) is automatically traced via OpenTelemetry spans
- Data is sent to Langfuse, where it can be visualized and analyzed

### How to configure

1. **Set environment variables in your `.env`:**

   ```env
   LANGFUSE_PUBLIC_KEY="pk-lf-..."   # Your Langfuse public key
   LANGFUSE_SECRET_KEY="sk-lf-..."   # Your Langfuse secret key
   OTEL_EXPORTER_OTLP_ENDPOINT="https://cloud.langfuse.com/api/public/otel" # (or us.cloud... for US region)
   ```

   > **Attention:** Do not swap the keys! `pk-...` is public, `sk-...` is secret.

2. **Automatic initialization**

   - Tracing is automatically initialized when the application starts (`src/main.py`).
   - Agent execution functions are already instrumented with spans (`src/services/agent_runner.py`).

3. **View in the Langfuse dashboard**
   - Access your Langfuse dashboard to see real-time traces.

### Troubleshooting

- **401 Error (Invalid credentials):**
  - Check if the keys are correct and not swapped in your `.env`.
  - Make sure the endpoint matches your region (EU or US).
- **Context error in async generator:**
  - The code is already adjusted to avoid OpenTelemetry context issues in async generators.
- **Questions about integration:**
  - See the [official Langfuse documentation - Google ADK](https://langfuse.com/docs/integrations/google-adk)

## 🤖 Agent 2 Agent (A2A) Protocol Support

Evo AI implements the Google's Agent 2 Agent (A2A) protocol, enabling seamless communication and interoperability between AI agents. This implementation includes:

### Key Features

- **Standardized Communication**: Agents can communicate using a common protocol regardless of their underlying implementation
- **Interoperability**: Support for agents built with different frameworks and technologies
- **Well-Known Endpoints**: Standardized endpoints for agent discovery and interaction
- **Task Management**: Support for task-based interactions between agents
- **State Management**: Tracking of agent states and conversation history
- **Authentication**: Secure API key-based authentication for agent interactions

### Implementation Details

- **Agent Card**: Each agent exposes a `.well-known/agent.json` endpoint with its capabilities and configuration
- **Task Handling**: Support for task creation, execution, and status tracking
- **Message Format**: Standardized message format for agent communication
- **History Tracking**: Maintains conversation history between agents
- **Artifact Management**: Support for handling different types of artifacts (text, files, etc.)

### Example Usage

```json
// Agent Card Example
{
  "name": "My Agent",
  "description": "A helpful AI assistant",
  "url": "https://api.example.com/agents/123",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  "authentication": {
    "schemes": ["apiKey"],
    "credentials": {
      "in": "header",
      "name": "x-api-key"
    }
  },
  "skills": [
    {
      "id": "search",
      "name": "Web Search",
      "description": "Search the web for information"
    }
  ]
}
```

For more information about the A2A protocol, visit [Google's A2A Protocol Documentation](https://google.github.io/A2A/).

## 📁 Project Structure

```
src/
├── api/          # API endpoints
├── core/         # Core business logic
├── models/       # Data models
├── schemas/      # Pydantic schemas for validation
├── services/     # Business services
├── templates/    # Email templates
│   └── emails/   # Jinja2 email templates
├── utils/        # Utilities
└── config/       # Configurations
```

## 📋 Prerequisites

Before starting, make sure you have the following installed:

- **Python**: 3.10 or higher
- **PostgreSQL**: 13.0 or higher
- **Redis**: 6.0 or higher
- **Git**: For version control
- **Make**: For running Makefile commands (usually pre-installed on Linux/Mac, for Windows use WSL or install via chocolatey)

You'll also need the following accounts/API keys:

- **OpenAI API Key**: Or API key from another AI provider
- **SendGrid Account**: For email functionality
- **Google API Key**: If using Google's A2A protocol implementation

## 📋 Requirements

- Python 3.10+
- PostgreSQL
- Redis
- OpenAI API Key (or other AI provider)
- SendGrid Account (for email sending)

## 🔧 Installation

1. Clone the repository:

```bash
git clone https://github.com/your-username/evo-ai.git
cd evo-ai
```

2. Create a virtual environment:

```bash
make venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

3. Install dependencies:

```bash
pip install -e .        # For basic installation
# or
pip install -e ".[dev]" # For development dependencies
```

Or using the Makefile:

```bash
make install      # For basic installation
# or
make install-dev  # For development dependencies
```

4. Set up environment variables:

```bash
cp .env.example .env
# Edit the .env file with your settings
```

5. Initialize the database and run migrations:

```bash
make alembic-upgrade
```

6. Seed the database with initial data:

```bash
make seed-all
```

## 🚀 Getting Started

After installation, follow these steps to set up your first agent:

1. **Configure MCP Server**: Set up your Model Control Protocol server configuration first
2. **Create Client or Register**: Create a new client or register a user account
3. **Create Agents**: Set up the agents according to your needs (LLM, A2A, Sequential, Parallel, Loop, or Workflow)

### Configuration (.env file)

Configure your environment using the following key settings:

```bash
# Database settings
POSTGRES_CONNECTION_STRING="postgresql://postgres:root@localhost:5432/evo_ai"

# Redis settings
REDIS_HOST="localhost"
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD="your-redis-password"

# JWT settings
JWT_SECRET_KEY="your-jwt-secret-key"
JWT_ALGORITHM="HS256"
JWT_EXPIRATION_TIME=30  # In seconds

# SendGrid for emails
SENDGRID_API_KEY="your-sendgrid-api-key"
EMAIL_FROM="noreply@yourdomain.com"
APP_URL="https://yourdomain.com"

# Encryption for API keys
ENCRYPTION_KEY="your-encryption-key"
```

### Project Dependencies

The project uses modern Python packaging standards with `pyproject.toml`. Key dependencies include:

```toml
dependencies = [
    "fastapi==0.115.12",
    "uvicorn==0.34.2",
    "pydantic==2.11.3",
    "sqlalchemy==2.0.40",
    "psycopg2==2.9.10",
    "alembic==1.15.2",
    "redis==5.3.0",
    "langgraph==0.4.1",
    # ... other dependencies
]
```

For development, additional packages can be installed with:

```bash
pip install -e ".[dev]"
```

This includes development tools like black, flake8, pytest, and more.

## 🔐 Authentication

The API uses JWT (JSON Web Token) authentication. To access the endpoints, you need to:

1. Register a user or log in to obtain a JWT token
2. Include the JWT token in the `Authorization` header of all requests in the format `Bearer <token>`
3. Tokens expire after a configured period (default: 30 minutes)

### Authentication Flow

1. **User Registration**:

```http
POST /api/v1/auth/register
```

2. **Email Verification**:
   An email will be sent containing a verification link.

3. **Login**:

```http
POST /api/v1/auth/login
```

Returns a JWT token to be used in requests.

4. **Password Recovery (if needed)**:

```http
POST /api/v1/auth/forgot-password
POST /api/v1/auth/reset-password
```

5. **Recover logged user data**:

```http
POST /api/v1/auth/me
```

### Example Usage with curl:

```bash
# Login
curl -X POST "http://localhost:8000/api/v1/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "your-email@example.com", "password": "your-password"}'

# Use received token
curl -X GET "http://localhost:8000/api/v1/clients/" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Access Control

- Regular users (associated with a client) only have access to their client's resources
- Admin users have access to all resources
- Certain operations (such as creating MCP servers) are restricted to administrators only
- Account lockout mechanism after multiple failed login attempts for enhanced security

## 📧 Email Templates

The platform uses Jinja2 templates for email rendering with a unified design system:

- **Base Template**: All emails extend a common base template for consistent styling
- **Verification Email**: Sent when users register to verify their email address
- **Password Reset**: Sent when users request a password reset
- **Welcome Email**: Sent after email verification to guide new users
- **Account Locked**: Security alert when an account is locked due to multiple failed login attempts

All email templates feature responsive design, clear call-to-action buttons, and fallback mechanisms.

## 🚀 Running the Project

```bash
make run         # For development with automatic reload
# or
make run-prod    # For production with multiple workers
```

The API will be available at `http://localhost:8000`

## 📚 API Documentation

The interactive API documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 📊 Logs and Audit

- Logs are stored in the `logs/` directory with the following format:
  - `{logger_name}_{date}.log`
- The system maintains audit logs for important administrative actions
- Each action is recorded with information such as user, IP, date/time, and details

## 🤝 Contributing

We welcome contributions from the community! Here's how you can help:

1. Fork the project
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Make your changes and add tests if possible
4. Run tests and make sure they pass
5. Commit your changes following conventional commits format (`feat: add amazing feature`)
6. Push to the branch (`git push origin feature/AmazingFeature`)
7. Open a Pull Request

Please read our [Contributing Guidelines](CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📊 Stargazers

[![Stargazers repo roster for @your-username/evo-ai](https://reporoster.com/stars/your-username/evo-ai)](https://github.com/your-username/evo-ai/stargazers)

## 🔄 Forks

[![Forkers repo roster for @your-username/evo-ai](https://reporoster.com/forks/your-username/evo-ai)](https://github.com/your-username/evo-ai/network/members)

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Google ADK](https://github.com/google/adk)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [ReactFlow](https://reactflow.dev/)

## 👨‍💻 Development Commands

```bash
# Database migrations
make init                       # Initialize Alembic
make alembic-revision message="description"  # Create new migration
make alembic-upgrade            # Update database to latest version (use to execute existing migrations)
make alembic-downgrade          # Revert latest migration
make alembic-migrate message="description"  # Create and apply migration
make alembic-reset              # Reset database

# Seeders
make seed-admin                 # Create default admin
make seed-client                # Create default client
make seed-mcp-servers           # Create example MCP servers
make seed-tools                 # Create example tools
make seed-all                   # Run all seeders

# Code verification
make lint                       # Verify code with flake8
make format                     # Format code with black
make clear-cache                # Clear project cache
```

## 🐳 Running with Docker

For quick setup and deployment, we provide Docker and Docker Compose configurations.

### Prerequisites

- Docker installed
- Docker Compose installed

### Configuration

1. Create and configure the `.env` file:

```bash
cp .env.example .env
# Edit the .env file with your settings, especially:
# - POSTGRES_CONNECTION_STRING
# - REDIS_HOST (should be "redis" when using Docker)
# - JWT_SECRET_KEY
# - SENDGRID_API_KEY
```

2. Build the Docker image:

```bash
make docker-build
```

3. Start the services (API, PostgreSQL, and Redis):

```bash
make docker-up
```

4. Apply migrations (first time only):

```bash
docker-compose exec api python -m alembic upgrade head
```

5. Populate the database with initial data:

```bash
make docker-seed
```

6. To check application logs:

```bash
make docker-logs
```

7. To stop the services:

```bash
make docker-down
```

### Available Services

- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Persistent Volumes

Docker Compose sets up persistent volumes for:

- PostgreSQL data
- Redis data
- Application logs directory

### Environment Variables

The main environment variables used by the API container:

- `POSTGRES_CONNECTION_STRING`: PostgreSQL connection string
- `REDIS_HOST`: Redis host (use "redis" when running with Docker)
- `JWT_SECRET_KEY`: Secret key for JWT token generation
- `SENDGRID_API_KEY`: SendGrid API key for sending emails
- `EMAIL_FROM`: Email used as sender
- `APP_URL`: Base URL of the application

## 🔒 Secure API Key Management

Evo AI implements a secure API key management system that protects sensitive credentials:

- **Encrypted Storage**: API keys are encrypted using Fernet symmetric encryption before storage
- **Secure References**: Agents reference API keys by UUID (api_key_id) instead of storing raw keys
- **Centralized Management**: API keys can be created, updated, and rotated without changing agent configurations
- **Client Isolation**: API keys are scoped to specific clients for better security isolation

### Encryption Configuration

The encryption system uses a secure key defined in the `.env` file:

```env
ENCRYPTION_KEY="your-secure-encryption-key"
```

If not provided, a secure key will be generated automatically at startup.

### API Key Management

API keys can be managed through dedicated endpoints:

```http
# Create a new API key
POST /api/v1/agents/apikeys
Content-Type: application/json
Authorization: Bearer your-token-jwt
x-client-id: client-uuid

{
  "client_id": "client-uuid",
  "name": "My OpenAI Key",
  "provider": "openai",
  "key_value": "sk-actual-api-key-value"
}

# List all API keys for a client
GET /api/v1/agents/apikeys
Authorization: Bearer your-token-jwt
x-client-id: client-uuid

# Get a specific API key
GET /api/v1/agents/apikeys/{key_id}
Authorization: Bearer your-token-jwt
x-client-id: client-uuid

# Update an API key
PUT /api/v1/agents/apikeys/{key_id}
Content-Type: application/json
Authorization: Bearer your-token-jwt
x-client-id: client-uuid

{
  "name": "Updated Key Name",
  "provider": "anthropic",
  "key_value": "new-key-value",
  "is_active": true
}

# Delete an API key (soft delete)
DELETE /api/v1/agents/apikeys/{key_id}
Authorization: Bearer your-token-jwt
x-client-id: client-uuid
```

## 🤖 Agent Organization

Agents can be organized into folders for better management:

### Creating and Managing Folders

```http
# Create a new folder
POST /api/v1/agents/folders
Content-Type: application/json
Authorization: Bearer your-token-jwt

{
  "client_id": "client-uuid",
  "name": "Marketing Agents",
  "description": "Agents for content marketing tasks"
}

# List all folders
GET /api/v1/agents/folders
Authorization: Bearer your-token-jwt
x-client-id: client-uuid

# Get a specific folder
GET /api/v1/agents/folders/{folder_id}
Authorization: Bearer your-token-jwt
x-client-id: client-uuid

# Update a folder
PUT /api/v1/agents/folders/{folder_id}
Content-Type: application/json
Authorization: Bearer your-token-jwt
x-client-id: client-uuid

{
  "name": "Updated Folder Name",
  "description": "Updated folder description"
}

# Delete a folder
DELETE /api/v1/agents/folders/{folder_id}
Authorization: Bearer your-token-jwt
x-client-id: client-uuid

# List agents in a folder
GET /api/v1/agents/folders/{folder_id}/agents
Authorization: Bearer your-token-jwt
x-client-id: client-uuid

# Assign an agent to a folder
PUT /api/v1/agents/{agent_id}/folder
Content-Type: application/json
Authorization: Bearer your-token-jwt
x-client-id: client-uuid

{
  "folder_id": "folder-uuid"
}

# Remove an agent from any folder
PUT /api/v1/agents/{agent_id}/folder
Content-Type: application/json
Authorization: Bearer your-token-jwt
x-client-id: client-uuid

{
  "folder_id": null
}
```

### Filtering Agents by Folder

When listing agents, you can filter by folder:

```http
GET /api/v1/agents?folder_id=folder-uuid
Authorization: Bearer your-token-jwt
x-client-id: client-uuid
```
