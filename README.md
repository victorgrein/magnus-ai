# Evo AI - AI Agents Platform

Evo AI is an open-source platform for creating and managing AI agents, enabling integration with different AI models and services.

## 🚀 Overview

The Evo AI platform allows:
- Creation and management of AI agents
- Integration with different language models
- Client and contact management
- MCP server configuration
- Custom tools management
- JWT authentication with email verification

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
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit the .env file with your settings
```

5. Run migrations:
```bash
make upgrade
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
make run
```

The API will be available at `http://localhost:8000`

## 📚 API Documentation

### Authentication

#### Register User
```http
POST /api/v1/auth/register
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123",
  "name": "Company Name"
}
```

**Response (201 Created):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "user@example.com",
  "client_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "is_active": false,
  "email_verified": false,
  "is_admin": false,
  "created_at": "2023-07-10T15:00:00.000Z"
}
```

Registers a new user and sends a verification email. The user will remain inactive until the email is verified.

#### Login
```http
POST /api/v1/auth/login
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

Authenticates the user and returns a valid JWT token for use in subsequent requests.

#### Recover logged user data
```http
POST /api/v1/auth/me
```

**Response (200 OK):**
```json
{
    "email": "user@example.com",
    "id": "777d7036-ebe7-4b79-9cc4-981fa0640d2a",
    "client_id": "161e054a-6654-4a2e-90dd-b2499685797a",
    "is_active": true,
    "email_verified": true,
    "is_admin": false,
    "created_at": "2025-04-28T18:56:42.832905Z"
}
```

#### Verify Email
```http
GET /api/v1/auth/verify-email/{token}
```

**Response (200 OK):**
```json
{
  "message": "Email successfully verified. Your account is now active."
}
```

Verifies the user's email using the token sent by email. Activates the user's account.

#### Resend Verification
```http
POST /api/v1/auth/resend-verification
```

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "message": "Verification email resent. Please check your inbox."
}
```

Resends the verification email for users with unverified email.

#### Forgot Password
```http
POST /api/v1/auth/forgot-password
```

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "message": "If the email exists in our database, a password reset link will be sent."
}
```

Sends an email with password recovery instructions if the email is registered.

#### Reset Password
```http
POST /api/v1/auth/reset-password
```

**Request Body:**
```json
{
  "token": "password-reset-token-received-by-email",
  "new_password": "newSecurePassword456"
}
```

**Response (200 OK):**
```json
{
  "message": "Password successfully reset."
}
```

Resets the user's password using the token received by email.

### Clients

#### Create Client
```http
POST /api/v1/clients/
```

**Request Body:**
```json
{
  "name": "Company Name",
  "email": "user@example.com"
}
```

**Response (201 Created):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "Company Name",
  "email": "user@example.com"
  "created_at": "2023-07-10T15:00:00.000Z"
}
```

Creates a new client. Requires administrator permissions.

#### List Clients
```http
GET /api/v1/clients/
```

**Query Parameters:**
- `skip` (optional): Number of records to skip (default: 0)
- `limit` (optional): Maximum number of records to return (default: 100)

**Response (200 OK):**
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "Company Name",
    "email": "user@example.com",
    "created_at": "2023-07-10T15:00:00.000Z"
  }
]
```

Lists all clients with pagination. For administrator users, returns all clients. For regular users, returns only the client they are associated with.

#### Get Client
```http
GET /api/v1/clients/{client_id}
```

**Response (200 OK):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "Company Name",
  "email": "user@example.com",
  "created_at": "2023-07-10T15:00:00.000Z"
}
```

Gets a specific client. The user must have permission to access this client.

#### Update Client
```http
PUT /api/v1/clients/{client_id}
```

**Request Body:**
```json
{
  "name": "New Company Name",
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "New Company Name",
  "email": "user@example.com",
  "created_at": "2023-07-10T15:00:00.000Z"
}
```

Updates client data. The user must have permission to access this client.

#### Delete Client
```http
DELETE /api/v1/clients/{client_id}
```

**Response (204 No Content)**

Deletes a client. Requires administrator permissions.

### Contacts

#### Create Contact
```http
POST /api/v1/contacts/
```

**Request Body:**
```json
{
  "client_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "ext_id": "optional-external-id",
  "name": "Contact Name",
  "meta": {
    "phone": "+15551234567",
    "category": "customer",
    "notes": "Additional information"
  }
}
```

**Response (201 Created):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "client_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "ext_id": "optional-external-id",
  "name": "Contact Name",
  "meta": {
    "phone": "+15551234567",
    "category": "customer",
    "notes": "Additional information"
  }
}
```

Creates a new contact. The user must have permission to access the specified client.

#### List Contacts
```http
GET /api/v1/contacts/{client_id}
```

**Query Parameters:**
- `skip` (optional): Number of records to skip (default: 0)
- `limit` (optional): Maximum number of records to return (default: 100)

**Response (200 OK):**
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "client_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "ext_id": "optional-external-id",
    "name": "Contact Name",
    "meta": {
      "phone": "+15551234567",
      "category": "customer"
    }
  }
]
```

Lists contacts of a client. The user must have permission to access this client.

#### Search Contact
```http
GET /contact/{contact_id}
```

#### Update Contact
```http
PUT /contact/{contact_id}
```
Updates contact data.

#### Remove Contact
```http
DELETE /contact/{contact_id}
```
Removes a contact.

### Agents

#### Create Agent
```http
POST /api/v1/agents/
```

**Request Body:**
```json
{
  "client_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "customer-service-agent",
  "description": "Agent for customer service",
  "type": "llm",
  "model": "claude-3-opus-20240229",
  "api_key": "your-api-key-here",
  "instruction": "You are a customer service assistant for company X. Always be polite and try to solve customer problems efficiently.",
  "config": {
    "temperature": 0.7,
    "max_tokens": 1024,
    "tools": ["web_search", "knowledge_base"]
  }
}
```

**Response (201 Created):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "client_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "customer-service-agent",
  "description": "Agent for customer service",
  "type": "llm",
  "model": "claude-3-opus-20240229",
  "api_key": "your-api-key-here",
  "instruction": "You are a customer service assistant for company X. Always be polite and try to solve customer problems efficiently.",
  "config": {
    "temperature": 0.7,
    "max_tokens": 1024,
    "tools": ["web_search", "knowledge_base"]
  },
  "created_at": "2023-07-10T15:00:00.000Z",
  "updated_at": "2023-07-10T15:00:00.000Z"
}
```

Creates a new agent. The user must have permission to access the specified client.

**Notes about agent types:**
- For `llm` type agents, the `model` and `api_key` fields are required
- For `sequential`, `parallel`, or `loop` type agents, the configuration must include a list of `sub_agents`

#### List Agents
```http
GET /api/v1/agents/{client_id}
```

**Query Parameters:**
- `skip` (optional): Number of records to skip (default: 0)
- `limit` (optional): Maximum number of records to return (default: 100)

**Response (200 OK):**
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "client_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "customer-service-agent",
    "description": "Agent for customer service",
    "type": "llm",
    "model": "claude-3-opus-20240229",
    "instruction": "You are a customer service assistant...",
    "config": {
      "temperature": 0.7,
      "max_tokens": 1024,
      "tools": ["web_search", "knowledge_base"]
    },
    "created_at": "2023-07-10T15:00:00.000Z",
    "updated_at": "2023-07-10T15:00:00.000Z"
  }
]
```

Lists all agents of a client. The user must have permission to access the specified client.

#### Get Agent
```http
GET /api/v1/agents/{agent_id}
```

**Response (200 OK):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "client_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "customer-service-agent",
  "description": "Agent for customer service",
  "type": "llm",
  "model": "claude-3-opus-20240229",
  "instruction": "You are a customer service assistant...",
  "config": {
    "temperature": 0.7,
    "max_tokens": 1024,
    "tools": ["web_search", "knowledge_base"]
  },
  "created_at": "2023-07-10T15:00:00.000Z",
  "updated_at": "2023-07-10T15:00:00.000Z"
}
```

Gets a specific agent. The user must have permission to access this agent.

#### Update Agent
```http
PUT /api/v1/agents/{agent_id}
```

**Request Body:**
```json
{
  "name": "new-customer-service-agent",
  "description": "Updated agent for customer service",
  "type": "llm",
  "model": "claude-3-sonnet-20240229",
  "instruction": "You are a customer service assistant for company X...",
  "config": {
    "temperature": 0.5,
    "max_tokens": 2048,
    "tools": ["web_search", "knowledge_base", "calculator"]
  }
}
```

**Response (200 OK):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "client_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "new-customer-service-agent",
  "description": "Updated agent for customer service",
  "type": "llm",
  "model": "claude-3-sonnet-20240229",
  "instruction": "You are a customer service assistant for company X...",
  "config": {
    "temperature": 0.5,
    "max_tokens": 2048,
    "tools": ["web_search", "knowledge_base", "calculator"]
  },
  "created_at": "2023-07-10T15:00:00.000Z",
  "updated_at": "2023-07-10T15:05:00.000Z"
}
```

Updates agent data. The user must have permission to access this agent.

#### Delete Agent
```http
DELETE /api/v1/agents/{agent_id}
```

**Response (204 No Content)**

Deletes an agent. The user must have permission to access this agent.

### MCP Servers

#### Create MCP Server
```http
POST /api/v1/mcp-servers/
```

**Request Body:**
```json
{
  "name": "openai-server",
  "description": "MCP server for OpenAI API access",
  "config_json": {
    "base_url": "https://api.openai.com/v1",
    "timeout": 30
  },
  "environments": {
    "OPENAI_API_KEY": "${OPENAI_API_KEY}"
  },
  "tools": ["web_search", "knowledge_base"],
  "type": "official"
}
```

**Response (201 Created):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "openai-server",
  "description": "MCP server for OpenAI API access",
  "config_json": {
    "base_url": "https://api.openai.com/v1",
    "timeout": 30
  },
  "environments": {
    "OPENAI_API_KEY": "${OPENAI_API_KEY}"
  },
  "tools": ["web_search", "knowledge_base"],
  "type": "official",
  "created_at": "2023-07-10T15:00:00.000Z",
  "updated_at": "2023-07-10T15:00:00.000Z"
}
```

Creates a new MCP server. Requires administrator permissions.

#### List MCP Servers
```http
GET /api/v1/mcp-servers/
```

**Query Parameters:**
- `skip` (optional): Number of records to skip (default: 0)
- `limit` (optional): Maximum number of records to return (default: 100)

**Response (200 OK):**
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "openai-server",
    "description": "MCP server for OpenAI API access",
    "config_json": {
      "base_url": "https://api.openai.com/v1",
      "timeout": 30
    },
    "environments": {
      "OPENAI_API_KEY": "${OPENAI_API_KEY}"
    },
    "tools": ["web_search", "knowledge_base"],
    "type": "official",
    "created_at": "2023-07-10T15:00:00.000Z",
    "updated_at": "2023-07-10T15:00:00.000Z"
  }
]
```

Lists all available MCP servers.

#### Get MCP Server
```http
GET /api/v1/mcp-servers/{server_id}
```

**Response (200 OK):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "openai-server",
  "description": "MCP server for OpenAI API access",
  "config_json": {
    "base_url": "https://api.openai.com/v1",
    "timeout": 30
  },
  "environments": {
    "OPENAI_API_KEY": "${OPENAI_API_KEY}"
  },
  "tools": ["web_search", "knowledge_base"],
  "type": "official",
  "created_at": "2023-07-10T15:00:00.000Z",
  "updated_at": "2023-07-10T15:00:00.000Z"
}
```

Gets a specific MCP server.

#### Update MCP Server
```http
PUT /api/v1/mcp-servers/{server_id}
```

**Request Body:**
```json
{
  "name": "updated-openai-server",
  "description": "Updated MCP server for OpenAI API access",
  "config_json": {
    "base_url": "https://api.openai.com/v1",
    "timeout": 60
  },
  "environments": {
    "OPENAI_API_KEY": "${OPENAI_API_KEY}",
    "OPENAI_ORG_ID": "${OPENAI_ORG_ID}"
  },
  "tools": ["web_search", "knowledge_base", "image_generation"],
  "type": "official"
}
```

**Response (200 OK):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "updated-openai-server",
  "description": "Updated MCP server for OpenAI API access",
  "config_json": {
    "base_url": "https://api.openai.com/v1",
    "timeout": 60
  },
  "environments": {
    "OPENAI_API_KEY": "${OPENAI_API_KEY}",
    "OPENAI_ORG_ID": "${OPENAI_ORG_ID}"
  },
  "tools": ["web_search", "knowledge_base", "image_generation"],
  "type": "official",
  "created_at": "2023-07-10T15:00:00.000Z",
  "updated_at": "2023-07-10T15:05:00.000Z"
}
```

Updates an MCP server. Requires administrator permissions.

#### Delete MCP Server
```http
DELETE /api/v1/mcp-servers/{server_id}
```

**Response (204 No Content)**

Deletes an MCP server. Requires administrator permissions.

### Tools

#### Create Tool
```http
POST /api/v1/tools/
```

**Request Body:**
```json
{
  "name": "web_search",
  "description": "Real-time web search",
  "config_json": {
    "api_url": "https://api.search.com",
    "max_results": 5
  },
  "environments": {
    "SEARCH_API_KEY": "${SEARCH_API_KEY}"
  }
}
```

**Response (201 Created):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "web_search",
  "description": "Real-time web search",
  "config_json": {
    "api_url": "https://api.search.com",
    "max_results": 5
  },
  "environments": {
    "SEARCH_API_KEY": "${SEARCH_API_KEY}"
  },
  "created_at": "2023-07-10T15:00:00.000Z",
  "updated_at": "2023-07-10T15:00:00.000Z"
}
```

Creates a new tool. Requires administrator permissions.

#### List Tools
```http
GET /api/v1/tools/
```

**Query Parameters:**
- `skip` (optional): Number of records to skip (default: 0)
- `limit` (optional): Maximum number of records to return (default: 100)

**Response (200 OK):**
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "web_search",
    "description": "Real-time web search",
    "config_json": {
      "api_url": "https://api.search.com",
      "max_results": 5
    },
    "environments": {
      "SEARCH_API_KEY": "${SEARCH_API_KEY}"
    },
    "created_at": "2023-07-10T15:00:00.000Z",
    "updated_at": "2023-07-10T15:00:00.000Z"
  }
]
```

Lists all available tools.

#### Get Tool
```http
GET /api/v1/tools/{tool_id}
```

**Response (200 OK):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "web_search",
  "description": "Real-time web search",
  "config_json": {
    "api_url": "https://api.search.com",
    "max_results": 5
  },
  "environments": {
    "SEARCH_API_KEY": "${SEARCH_API_KEY}"
  },
  "created_at": "2023-07-10T15:00:00.000Z",
  "updated_at": "2023-07-10T15:00:00.000Z"
}
```

Gets a specific tool.

#### Update Tool
```http
PUT /api/v1/tools/{tool_id}
```

**Request Body:**
```json
{
  "name": "web_search_pro",
  "description": "Real-time web search with advanced filters",
  "config_json": {
    "api_url": "https://api.search.com/v2",
    "max_results": 10,
    "filters": {
      "safe_search": true,
      "time_range": "week"
    }
  },
  "environments": {
    "SEARCH_API_KEY": "${SEARCH_API_KEY}"
  }
}
```

**Response (200 OK):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "web_search_pro",
  "description": "Real-time web search with advanced filters",
  "config_json": {
    "api_url": "https://api.search.com/v2",
    "max_results": 10,
    "filters": {
      "safe_search": true,
      "time_range": "week"
    }
  },
  "environments": {
    "SEARCH_API_KEY": "${SEARCH_API_KEY}"
  },
  "created_at": "2023-07-10T15:00:00.000Z",
  "updated_at": "2023-07-10T15:05:00.000Z"
}
```

Updates a tool. Requires administrator permissions.

#### Delete Tool
```http
DELETE /api/v1/tools/{tool_id}
```

**Response (204 No Content)**

Deletes a tool. Requires administrator permissions.

### Chat

#### Send Message
```http
POST /api/v1/chat
```

**Request Body:**
```json
{
  "agent_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "contact_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "message": "Hello, I need help with my order."
}
```

**Response (200 OK):**
```json
{
  "response": "Hello! Of course, I'm here to help with your order. Could you please provide your order number or more details about the issue you're experiencing?",
  "status": "success",
  "timestamp": "2023-07-10T15:00:00.000Z"
}
```

Sends a message to an agent and returns the generated response. The user must have permission to access the specified agent and contact.

#### Conversation History
```http
GET /api/v1/chat/history/{contact_id}
```

**Query Parameters:**
- `agent_id` (optional): Filter by a specific agent
- `start_date` (optional): Start date in ISO 8601 format
- `end_date` (optional): End date in ISO 8601 format
- `skip` (optional): Number of records to skip (default: 0)
- `limit` (optional): Maximum number of records to return (default: 100)

**Response (200 OK):**
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "agent_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "contact_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "message": "Hello, I need help with my order.",
    "response": "Hello! Of course, I'm here to help with your order. Could you please provide your order number or more details about the issue you're experiencing?",
    "timestamp": "2023-07-10T15:00:00.000Z"
  }
]
```

Retrieves the conversation history of a specific contact. The user must have permission to access the specified contact.

### Administration

#### Audit Logs
```http
GET /api/v1/admin/audit-logs
```

**Query Parameters:**
- `user_id` (optional): Filter by user
- `action` (optional): Filter by action type
- `start_date` (optional): Start date in ISO 8601 format
- `end_date` (optional): End date in ISO 8601 format
- `resource_type` (optional): Type of affected resource
- `skip` (optional): Number of records to skip (default: 0)
- `limit` (optional): Maximum number of records to return (default: 100)

**Response (200 OK):**
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "action": "CREATE",
    "resource_type": "AGENT",
    "resource_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "timestamp": "2023-07-10T15:00:00.000Z",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "details": {
      "before": null,
      "after": {
        "name": "customer-service-agent",
        "type": "llm"
      }
    }
  }
]
```

Retrieves audit logs. Requires administrator permissions.

#### List Administrators
```http
GET /api/v1/admin/users
```

**Query Parameters:**
- `skip` (optional): Number of records to skip (default: 0)
- `limit` (optional): Maximum number of records to return (default: 100)

**Response (200 OK):**
```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "admin@example.com",
    "name": "Administrator",
    "is_active": true,
    "email_verified": true,
    "is_admin": true,
    "created_at": "2023-07-10T15:00:00.000Z"
  }
]
```

Lists all administrator users. Requires administrator permissions.

#### Create Administrator
```http
POST /api/v1/admin/users
```

**Request Body:**
```json
{
  "email": "new_admin@example.com",
  "password": "securePassword123",
  "name": "New Administrator"
}
```

**Response (201 Created):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "new_admin@example.com",
  "name": "New Administrator",
  "is_active": true,
  "email_verified": true,
  "is_admin": true,
  "created_at": "2023-07-10T15:00:00.000Z"
}
```

Creates a new administrator user. Requires administrator permissions.

#### Deactivate Administrator
```http
DELETE /api/v1/admin/users/{user_id}
```

**Response (204 No Content)**

Deactivates an administrator user. Requires administrator permissions. The user is not removed from the database, just marked as inactive.

## 📝 Interactive Documentation

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

## Executando com Docker

Para facilitar a implantação e execução da aplicação, fornecemos configurações para Docker e Docker Compose.

### Pré-requisitos

- Docker instalado
- Docker Compose instalado

### Configuração

1. Configure as variáveis de ambiente necessárias no arquivo `.env` na raiz do projeto (ou use variáveis de ambiente do sistema)

2. Construa a imagem Docker:
```bash
make docker-build
```

3. Inicie os serviços (API, PostgreSQL e Redis):
```bash
make docker-up
```

4. Popule o banco de dados com dados iniciais:
```bash
make docker-seed
```

5. Para verificar os logs da aplicação:
```bash
make docker-logs
```

6. Para parar os serviços:
```bash
make docker-down
```

### Serviços Disponíveis

- **API**: http://localhost:8000
- **Documentação da API**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Volumes Persistentes

O Docker Compose configura volumes persistentes para:
- Dados do PostgreSQL
- Dados do Redis
- Diretório de logs da aplicação

### Variáveis de Ambiente

As principais variáveis de ambiente usadas pelo contêiner da API:

- `POSTGRES_CONNECTION_STRING`: String de conexão com o PostgreSQL
- `REDIS_HOST`: Host do Redis
- `JWT_SECRET_KEY`: Chave secreta para geração de tokens JWT
- `SENDGRID_API_KEY`: Chave da API do SendGrid para envio de emails
- `EMAIL_FROM`: Email usado como remetente
- `APP_URL`: URL base da aplicação