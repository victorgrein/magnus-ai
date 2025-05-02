# Evo AI - AI Agents Platform

Evo AI is an free platform for creating and managing AI agents, enabling integration with different AI models and services.

## 🚀 Overview

The Evo AI platform allows:

- Creation and management of AI agents
- Integration with different language models
- Client and contact management
- MCP server configuration
- Custom tools management
- JWT authentication with email verification
- **Agent 2 Agent (A2A) Protocol Support**: Interoperability between AI agents following Google's A2A specification

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
  "api_key": "your-api-key",
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
  "config": {
    "sub_agents": ["sub-agent-uuid"],
    "max_iterations": 5
  }
}
```

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

## 📋 Requirements

- Python 3.8+
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
make install      # For basic installation
# or
make install-dev  # For development dependencies
```

4. Set up environment variables:

```bash
cp .env.example .env
# Edit the .env file with your settings
```

5. Run migrations:

```bash
make alembic-upgrade
```

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

1. Fork the project
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Google ADK](https://github.com/google/adk)

## 👨‍💻 Development Commands

```bash
# Database migrations
make init                       # Initialize Alembic
make alembic-revision message="description"  # Create new migration
make alembic-upgrade            # Update database to latest version
make alembic-downgrade          # Revert latest migration
make alembic-migrate message="description"  # Create and apply migration
make alembic-reset              # Reset database

# Seeders
make seed-admin                 # Create default admin
make seed-client                # Create default client
make seed-agents                # Create example agents
make seed-mcp-servers           # Create example MCP servers
make seed-tools                 # Create example tools
make seed-contacts              # Create example contacts
make seed-all                   # Run all seeders

# Code verification
make lint                       # Verify code with flake8
make format                     # Format code with black
make clear-cache                # Clear project cache
```

## 🐳 Running with Docker

To facilitate deployment and execution of the application, we provide Docker and Docker Compose configurations.

### Prerequisites

- Docker installed
- Docker Compose installed

### Configuration

1. Configure the necessary environment variables in the `.env` file at the root of the project (or use system environment variables)

2. Build the Docker image:

```bash
make docker-build
```

3. Start the services (API, PostgreSQL, and Redis):

```bash
make docker-up
```

4. Populate the database with initial data:

```bash
make docker-seed
```

5. To check application logs:

```bash
make docker-logs
```

6. To stop the services:

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
- `REDIS_HOST`: Redis host
- `JWT_SECRET_KEY`: Secret key for JWT token generation
- `SENDGRID_API_KEY`: SendGrid API key for sending emails
- `EMAIL_FROM`: Email used as sender
- `APP_URL`: Base URL of the application
