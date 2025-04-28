import os
import sys
from pathlib import Path

# Add the root directory to PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config.database import engine, Base
from src.api.auth_routes import router as auth_router
from src.api.admin_routes import router as admin_router
from src.api.chat_routes import router as chat_router
from src.api.session_routes import router as session_router
from src.api.agent_routes import router as agent_router
from src.api.contact_routes import router as contact_router
from src.api.mcp_server_routes import router as mcp_server_router
from src.api.tool_routes import router as tool_router
from src.api.client_routes import router as client_router
from src.config.settings import settings
from src.utils.logger import setup_logger
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.sessions import DatabaseSessionService
from google.adk.memory import InMemoryMemoryService

# Configure logger
logger = setup_logger(__name__)


session_service = DatabaseSessionService(db_url=settings.POSTGRES_CONNECTION_STRING)
artifacts_service = InMemoryArtifactService()
memory_service = InMemoryMemoryService()

# FastAPI initialization
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PostgreSQL configuration
POSTGRES_CONNECTION_STRING = os.getenv(
    "POSTGRES_CONNECTION_STRING",
    "postgresql://postgres:root@localhost:5432/evo_ai"
)

# Create database tables
Base.metadata.create_all(bind=engine)

API_PREFIX = "/api/v1"

# Include routes
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX)
app.include_router(mcp_server_router, prefix=API_PREFIX)
app.include_router(tool_router, prefix=API_PREFIX)
app.include_router(client_router, prefix=API_PREFIX)
app.include_router(chat_router, prefix=API_PREFIX)
app.include_router(session_router, prefix=API_PREFIX)
app.include_router(agent_router, prefix=API_PREFIX)
app.include_router(contact_router, prefix=API_PREFIX)


@app.get("/")
def read_root():
    return {
        "message": "Welcome to Evo AI API",
        "documentation": "/docs",
        "version": settings.API_VERSION,
        "auth": "To access the API, use JWT authentication via '/api/v1/auth/login'"
    }
