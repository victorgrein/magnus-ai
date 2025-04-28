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
make venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

3. Install dependencies:

```bash
make install      # Para instalação básica
# ou
make install-dev  # Para instalação com dependências de desenvolvimento
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
make run         # Para desenvolvimento com reload automático
# ou
make run-prod    # Para produção com múltiplos workers
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
make init                       # Inicializar Alembic
make alembic-revision message="description"  # Criar nova migração
make alembic-upgrade            # Atualizar banco para última versão
make alembic-downgrade          # Reverter última migração
make alembic-migrate message="description"  # Criar e aplicar migração
make alembic-reset              # Resetar banco de dados

# Seeders
make seed-admin                 # Criar administrador padrão
make seed-client                # Criar cliente padrão
make seed-agents                # Criar agentes de exemplo
make seed-mcp-servers           # Criar servidores MCP de exemplo
make seed-tools                 # Criar ferramentas de exemplo
make seed-contacts              # Criar contatos de exemplo
make seed-all                   # Executar todos os seeders

# Verificação de código
make lint                       # Verificar código com flake8
make format                     # Formatar código com black
make clear-cache                # Limpar cache do projeto
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
