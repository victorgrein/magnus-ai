# Evo AI - System Architecture

This document provides an overview of the Evo AI system architecture, explaining how different components interact and the design decisions behind the implementation.

## High-Level Architecture

Evo AI follows a layered architecture pattern with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                          Client                             │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI REST API Layer                   │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │
│  │  API Routes │   │  Middleware │   │  Exception  │       │
│  │             │   │             │   │  Handlers   │       │
│  └─────────────┘   └─────────────┘   └─────────────┘       │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                            │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │
│  │   Agent     │   │   User      │   │    MCP      │       │
│  │  Services   │   │  Services   │   │  Services   │       │
│  └─────────────┘   └─────────────┘   └─────────────┘       │
│                                                             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │
│  │   Client    │   │   Contact   │   │   Tool      │       │
│  │  Services   │   │  Services   │   │  Services   │       │
│  └─────────────┘   └─────────────┘   └─────────────┘       │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Access Layer                        │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │
│  │  SQLAlchemy │   │   Alembic   │   │    Redis    │       │
│  │     ORM     │   │ Migrations  │   │    Cache    │       │
│  └─────────────┘   └─────────────┘   └─────────────┘       │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  External Storage Systems                   │
│  ┌─────────────┐   ┌─────────────┐                          │
│  │ PostgreSQL  │   │    Redis    │                          │
│  └─────────────┘   └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### API Layer

The API Layer is implemented using FastAPI and handles all HTTP requests and responses. Key components include:

1. **API Routes** (`src/api/`):
   - Defines all endpoints for the REST API
   - Handles request validation using Pydantic models
   - Manages authentication and authorization
   - Delegates business logic to the Service Layer

2. **Middleware** (`src/core/`):
   - JWT Authentication middleware
   - Error handling middleware
   - Request logging middleware

3. **Exception Handling**:
   - Centralized error handling with appropriate HTTP status codes
   - Standardized error responses

### Service Layer

The Service Layer contains the core business logic of the application. It includes:

1. **Agent Service** (`src/services/agent_service.py`):
   - Agent creation, configuration, and management
   - Integration with LLM providers

2. **Client Service** (`src/services/client_service.py`):
   - Client management functionality
   - Client resource access control

3. **MCP Server Service** (`src/services/mcp_server_service.py`):
   - Management of Multi-provider Cognitive Processing (MCP) servers
   - Configuration of server environments and tools

4. **User Service** (`src/services/user_service.py`):
   - User management and authentication
   - Email verification

5. **Additional Services**:
   - Contact Service
   - Tool Service
   - Email Service
   - Audit Service

### Data Access Layer

The Data Access Layer manages all interactions with the database and caching systems:

1. **SQLAlchemy ORM** (`src/models/`):
   - Defines database models and relationships
   - Provides methods for CRUD operations
   - Implements transactions and error handling

2. **Alembic Migrations**:
   - Manages database schema changes
   - Handles version control for database schema

3. **Redis Cache**:
   - Stores session data
   - Caches frequently accessed data
   - Manages JWT token blacklisting

### External Systems

1. **PostgreSQL**:
   - Primary relational database
   - Stores all persistent data
   - Manages relationships between entities

2. **Redis**:
   - Secondary database for caching
   - Session management
   - Rate limiting support

3. **Email System** (SendGrid):
   - Handles email notifications
   - Manages email templates
   - Provides delivery tracking

## Authentication Flow

```
┌─────────┐       ┌────────────┐      ┌──────────────┐      ┌─────────────┐
│  User   │       │  API Layer │      │ Auth Service │      │ User Service│
└────┬────┘       └──────┬─────┘      └──────┬───────┘      └──────┬──────┘
     │  Login Request    │                   │                     │
     │──────────────────>│                   │                     │
     │                   │ Authenticate User │                     │
     │                   │──────────────────>│                     │
     │                   │                   │  Validate Credentials
     │                   │                   │────────────────────>│
     │                   │                   │                     │
     │                   │                   │      Result         │
     │                   │                   │<────────────────────│
     │                   │                   │                     │
     │                   │ Generate JWT Token│                     │
     │                   │<──────────────────│                     │
     │  JWT Token        │                   │                     │
     │<──────────────────│                   │                     │
     │                   │                   │                     │
```

## Data Model

The core entities in the system are:

1. **Users**: Application users with authentication information
2. **Clients**: Organizations or accounts using the system
3. **Agents**: AI agents with configurations and capabilities
4. **Contacts**: End-users interacting with agents
5. **MCP Servers**: Server configurations for different AI providers
6. **Tools**: Tools that can be used by agents

The relationships between these entities are described in detail in the `DATA_MODEL.md` document.

## Security Considerations

1. **Authentication**:
   - JWT-based authentication with short-lived tokens
   - Secure password hashing with bcrypt
   - Email verification for new accounts
   - Account lockout after multiple failed attempts

2. **Authorization**:
   - Role-based access control (admin vs regular users)
   - Resource-based access control (client-specific resources)
   - JWT payload containing essential user data for quick authorization checks

3. **Data Protection**:
   - Environment variables for sensitive data
   - Encrypted connections to databases
   - No storage of plaintext passwords or API keys

## Deployment Architecture

Evo AI can be deployed using Docker containers for easier scaling and management:

```
┌─────────────────────────────────────────────────────────────┐
│                   Load Balancer                             │
└─────────────────────────────────────────────────────────────┘
                 │                 │
     ┌───────────┘                 └───────────┐
     ▼                                         ▼
┌──────────┐                              ┌──────────┐
│ API      │                              │ API      │
│ Container│                              │ Container│
└──────────┘                              └──────────┘
     │                                         │
     └───────────┐                 ┌───────────┘
                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                   PostgreSQL Cluster                        │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                   Redis Cluster                             │
└─────────────────────────────────────────────────────────────┘
```

## Further Reading

- See `DATA_MODEL.md` for detailed database schema information
- See `API_FLOW.md` for common API interaction patterns
- See `DEPLOYMENT.md` for deployment instructions and configurations 