# Evo AI - API Flows

This document describes common API flows and usage patterns for the Evo AI platform.

## Authentication Flow

### User Registration and Verification

```mermaid
sequenceDiagram
    Client->>API: POST /api/v1/auth/register
    API->>Database: Create user (inactive)
    API->>Email Service: Send verification email
    API-->>Client: Return user details
    Client->>API: GET /api/v1/auth/verify-email/{token}
    API->>Database: Activate user
    API-->>Client: Return success message
```

### Login Flow

```mermaid
sequenceDiagram
    Client->>API: POST /api/v1/auth/login
    API->>Database: Validate credentials
    API->>Auth Service: Generate JWT token
    API-->>Client: Return JWT token
    Client->>API: Request with Authorization header
    API->>Auth Middleware: Validate token
    API-->>Client: Return protected resource
```

### Password Recovery

```mermaid
sequenceDiagram
    Client->>API: POST /api/v1/auth/forgot-password
    API->>Database: Find user by email
    API->>Email Service: Send password reset email
    API-->>Client: Return success message
    Client->>API: POST /api/v1/auth/reset-password
    API->>Auth Service: Validate reset token
    API->>Database: Update password
    API-->>Client: Return success message
```

## Agent Management

### Creating and Using an Agent

```mermaid
sequenceDiagram
    Client->>API: POST /api/v1/agents/
    API->>Database: Create agent
    API-->>Client: Return agent details
    Client->>API: POST /api/v1/chat
    API->>Agent Service: Process message
    Agent Service->>External LLM: Send prompt
    External LLM-->>Agent Service: Return response
    Agent Service->>Database: Store conversation
    API-->>Client: Return agent response
```

### Sequential Agent Flow

```mermaid
sequenceDiagram
    Client->>API: POST /api/v1/chat (sequential agent)
    API->>Agent Service: Process message
    Agent Service->>Sub-Agent 1: Process first step
    Sub-Agent 1-->>Agent Service: Return intermediate result
    Agent Service->>Sub-Agent 2: Process with previous result
    Sub-Agent 2-->>Agent Service: Return intermediate result
    Agent Service->>Sub-Agent 3: Process final step
    Sub-Agent 3-->>Agent Service: Return final result
    Agent Service->>Database: Store conversation
    API-->>Client: Return final response
```

## Client and Contact Management

### Client Creation and Management

```mermaid
sequenceDiagram
    Admin->>API: POST /api/v1/clients/
    API->>Database: Create client
    API-->>Admin: Return client details
    Admin->>API: PUT /api/v1/clients/{client_id}
    API->>Database: Update client
    API-->>Admin: Return updated client
    Client User->>API: GET /api/v1/clients/
    API->>Auth Service: Check permissions
    API->>Database: Fetch client(s)
    API-->>Client User: Return client details
```

### Contact Management

```mermaid
sequenceDiagram
    Client User->>API: POST /api/v1/contacts/
    API->>Auth Service: Check permissions
    API->>Database: Create contact
    API-->>Client User: Return contact details
    Client User->>API: GET /api/v1/contacts/{client_id}
    API->>Auth Service: Check permissions
    API->>Database: Fetch contacts
    API-->>Client User: Return contact list
    Client User->>API: POST /api/v1/chat
    API->>Database: Validate contact belongs to client
    API->>Agent Service: Process message
    API-->>Client User: Return agent response
```

## MCP Server and Tool Management

### MCP Server Configuration

```mermaid
sequenceDiagram
    Admin->>API: POST /api/v1/mcp-servers/
    API->>Auth Service: Verify admin permissions
    API->>Database: Create MCP server
    API-->>Admin: Return server details
    Admin->>API: PUT /api/v1/mcp-servers/{server_id}
    API->>Auth Service: Verify admin permissions
    API->>Database: Update server configuration
    API-->>Admin: Return updated server
```

### Tool Configuration and Usage

```mermaid
sequenceDiagram
    Admin->>API: POST /api/v1/tools/
    API->>Auth Service: Verify admin permissions
    API->>Database: Create tool
    API-->>Admin: Return tool details
    Client User->>API: POST /api/v1/chat (with tool)
    API->>Agent Service: Process message
    Agent Service->>Tool Service: Execute tool
    Tool Service->>External API: Make external call
    External API-->>Tool Service: Return result
    Tool Service-->>Agent Service: Return tool result
    Agent Service-->>API: Return final response
    API-->>Client User: Return agent response
```

## Audit and Monitoring

### Audit Log Flow

```mermaid
sequenceDiagram
    User->>API: Perform administrative action
    API->>Auth Service: Verify permissions
    API->>Audit Service: Log action
    Audit Service->>Database: Store audit record
    API->>Database: Perform action
    API-->>User: Return action result
    Admin->>API: GET /api/v1/admin/audit-logs
    API->>Auth Service: Verify admin permissions
    API->>Database: Fetch audit logs
    API-->>Admin: Return audit history
```

## Error Handling

### Common Error Flows

```mermaid
sequenceDiagram
    Client->>API: Invalid request
    API->>Middleware: Process request
    Middleware->>Exception Handler: Handle validation error
    Exception Handler-->>Client: Return 422 Validation Error
    Client->>API: Request protected resource
    API->>Auth Middleware: Validate JWT
    Auth Middleware->>Exception Handler: Handle authentication error
    Exception Handler-->>Client: Return 401 Unauthorized
    Client->>API: Request resource without permission
    API->>Auth Service: Check resource permissions
    Auth Service->>Exception Handler: Handle permission error
    Exception Handler-->>Client: Return 403 Forbidden
```

## API Integration Best Practices

1. **Authentication**:
   - Store JWT tokens securely
   - Implement token refresh mechanism
   - Handle token expiration gracefully

2. **Error Handling**:
   - Implement proper error handling for all API calls
   - Pay attention to HTTP status codes
   - Log detailed error information for debugging

3. **Resource Management**:
   - Use pagination for listing resources
   - Filter only the data you need
   - Consider implementing client-side caching for frequently accessed data

4. **Agent Configuration**:
   - Start with preset agent templates
   - Test agent configurations with sample data
   - Monitor and adjust agent parameters based on performance

5. **Security**:
   - Never expose API keys or tokens in client-side code
   - Validate all user input before sending to the API
   - Implement proper permission checks in your application 