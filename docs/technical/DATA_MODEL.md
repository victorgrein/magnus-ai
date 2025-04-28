# Evo AI - Data Model

This document describes the database schema and entity relationships in the Evo AI platform.

## Database Schema

The Evo AI platform uses PostgreSQL as its primary database. Below is a detailed description of each table and its relationships.

## Entity Relationship Diagram

```
┌───────────┐      ┌───────────┐      ┌───────────┐
│           │      │           │      │           │
│   User    │──┐   │  Client   │◄─────│   Agent   │
│           │  │   │           │      │           │
└───────────┘  │   └───────────┘      └───────────┘
                │         ▲                  ▲
                │         │                  │
                └────────►│                  │
                          │                  │
                 ┌────────┴──────┐          │
                 │               │          │
                 │   Contact     │─────────┐│
                 │               │         ││
                 └───────────────┘         ││
                                           ││
                 ┌───────────────┐         ││
                 │               │◄────────┘│
                 │    Tool       │          │
                 │               │          │
                 └───────────────┘          │
                                            │
                 ┌───────────────┐          │
                 │               │◄─────────┘
                 │  MCP Server   │
                 │               │
                 └───────────────┘
```

## Tables

### User

The User table stores information about system users.

```sql
CREATE TABLE user (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    client_id UUID REFERENCES client(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT false,
    email_verified BOOLEAN DEFAULT false,
    is_admin BOOLEAN DEFAULT false,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

- **id**: Unique identifier (UUID)
- **email**: User's email address (unique)
- **password_hash**: Bcrypt-hashed password
- **client_id**: Reference to the client organization (null for admin users)
- **is_active**: Whether the user is active
- **email_verified**: Whether the email has been verified
- **is_admin**: Whether the user has admin privileges
- **failed_login_attempts**: Counter for failed login attempts
- **locked_until**: Timestamp until when the account is locked
- **created_at**: Creation timestamp
- **updated_at**: Last update timestamp

### Client

The Client table stores information about client organizations.

```sql
CREATE TABLE client (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

- **id**: Unique identifier (UUID)
- **name**: Client name
- **email**: Client email contact
- **created_at**: Creation timestamp
- **updated_at**: Last update timestamp

### Agent

The Agent table stores information about AI agents.

```sql
CREATE TABLE agent (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL REFERENCES client(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL,
    model VARCHAR(255),
    api_key TEXT,
    instruction TEXT,
    config_json JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

- **id**: Unique identifier (UUID)
- **client_id**: Reference to the client that owns this agent
- **name**: Agent name
- **description**: Agent description
- **type**: Agent type (e.g., "llm", "sequential", "parallel", "loop")
- **model**: LLM model name (for "llm" type agents)
- **api_key**: API key for the model provider (encrypted)
- **instruction**: System instructions for the agent
- **config_json**: JSON configuration specific to the agent type
- **created_at**: Creation timestamp
- **updated_at**: Last update timestamp

### Contact

The Contact table stores information about end-users that interact with agents.

```sql
CREATE TABLE contact (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL REFERENCES client(id) ON DELETE CASCADE,
    ext_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    meta JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

- **id**: Unique identifier (UUID)
- **client_id**: Reference to the client that owns this contact
- **ext_id**: Optional external ID for integration
- **name**: Contact name
- **meta**: Additional metadata in JSON format
- **created_at**: Creation timestamp
- **updated_at**: Last update timestamp

### MCP Server

The MCP Server table stores information about Multi-provider Cognitive Processing servers.

```sql
CREATE TABLE mcp_server (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    config_json JSONB NOT NULL DEFAULT '{}',
    environments JSONB NOT NULL DEFAULT '{}',
    tools JSONB NOT NULL DEFAULT '[]',
    type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

- **id**: Unique identifier (UUID)
- **name**: Server name
- **description**: Server description
- **config_json**: JSON configuration for the server
- **environments**: Environment variables as JSON
- **tools**: List of tools supported by this server
- **type**: Server type (e.g., "official", "custom")
- **created_at**: Creation timestamp
- **updated_at**: Last update timestamp

### Tool

The Tool table stores information about tools that can be used by agents.

```sql
CREATE TABLE tool (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    config_json JSONB NOT NULL DEFAULT '{}',
    environments JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

- **id**: Unique identifier (UUID)
- **name**: Tool name
- **description**: Tool description
- **config_json**: JSON configuration for the tool
- **environments**: Environment variables as JSON
- **created_at**: Creation timestamp
- **updated_at**: Last update timestamp

### Conversation

The Conversation table stores chat history between contacts and agents.

```sql
CREATE TABLE conversation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    response TEXT NOT NULL,
    meta JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

- **id**: Unique identifier (UUID)
- **agent_id**: Reference to the agent
- **contact_id**: Reference to the contact
- **message**: Message sent by the contact
- **response**: Response generated by the agent
- **meta**: Additional metadata (e.g., tokens used, tools called)
- **created_at**: Creation timestamp

### Audit Log

The Audit Log table stores records of administrative actions.

```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES "user"(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    details JSONB NOT NULL DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

- **id**: Unique identifier (UUID)
- **user_id**: Reference to the user who performed the action
- **action**: Type of action (e.g., "CREATE", "UPDATE", "DELETE")
- **resource_type**: Type of resource affected (e.g., "AGENT", "CLIENT")
- **resource_id**: Identifier of the affected resource
- **details**: JSON with before/after state
- **ip_address**: IP address of the user
- **user_agent**: User-agent string
- **created_at**: Creation timestamp

## Indexes

To optimize performance, the following indexes are created:

```sql
-- User indexes
CREATE INDEX idx_user_email ON "user" (email);
CREATE INDEX idx_user_client_id ON "user" (client_id);

-- Agent indexes
CREATE INDEX idx_agent_client_id ON agent (client_id);
CREATE INDEX idx_agent_name ON agent (name);

-- Contact indexes
CREATE INDEX idx_contact_client_id ON contact (client_id);
CREATE INDEX idx_contact_ext_id ON contact (ext_id);

-- Conversation indexes
CREATE INDEX idx_conversation_agent_id ON conversation (agent_id);
CREATE INDEX idx_conversation_contact_id ON conversation (contact_id);
CREATE INDEX idx_conversation_created_at ON conversation (created_at);

-- Audit log indexes
CREATE INDEX idx_audit_log_user_id ON audit_log (user_id);
CREATE INDEX idx_audit_log_resource_type ON audit_log (resource_type);
CREATE INDEX idx_audit_log_resource_id ON audit_log (resource_id);
CREATE INDEX idx_audit_log_created_at ON audit_log (created_at);
```

## Relationships

1. **User to Client**: Many-to-one relationship. Each user belongs to at most one client (except for admin users).

2. **Client to Agent**: One-to-many relationship. Each client can have multiple agents.

3. **Client to Contact**: One-to-many relationship. Each client can have multiple contacts.

4. **Agent to Conversation**: One-to-many relationship. Each agent can have multiple conversations.

5. **Contact to Conversation**: One-to-many relationship. Each contact can have multiple conversations.

6. **User to Audit Log**: One-to-many relationship. Each user can have multiple audit logs.

## Data Security

1. **Passwords**: All passwords are hashed using bcrypt before storage.

2. **API Keys**: API keys are stored with encryption.

3. **Sensitive Data**: Sensitive data in JSON fields is encrypted where appropriate.

4. **Cascading Deletes**: When a parent record is deleted, related records are automatically deleted to maintain referential integrity.

## Notes on JSONB Fields

PostgreSQL's JSONB fields provide flexibility for storing semi-structured data:

1. **config_json**: Used to store configuration parameters that may vary by agent type or tool.

2. **meta**: Used to store additional attributes that don't warrant their own columns.

3. **environments**: Used to store environment variables needed for tools and MCP servers.

This approach allows for extensibility without requiring database schema changes. 