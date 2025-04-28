import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config.database import engine, Base
from src.config.settings import settings
from src.utils.logger import setup_logger

# Necessary for other modules
from src.services.service_providers import session_service  # noqa: F401
from src.services.service_providers import artifacts_service  # noqa: F401
from src.services.service_providers import memory_service  # noqa: F401

import src.api.auth_routes
import src.api.admin_routes
import src.api.chat_routes
import src.api.session_routes
import src.api.agent_routes
import src.api.contact_routes
import src.api.mcp_server_routes
import src.api.tool_routes
import src.api.client_routes

# Add the root directory to PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# Configure logger
logger = setup_logger(__name__)

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
    "POSTGRES_CONNECTION_STRING", "postgresql://postgres:root@localhost:5432/evo_ai"
)

# Create database tables
Base.metadata.create_all(bind=engine)

API_PREFIX = "/api/v1"

# Define router references
auth_router = src.api.auth_routes.router
admin_router = src.api.admin_routes.router
chat_router = src.api.chat_routes.router
session_router = src.api.session_routes.router
agent_router = src.api.agent_routes.router
contact_router = src.api.contact_routes.router
mcp_server_router = src.api.mcp_server_routes.router
tool_router = src.api.tool_routes.router
client_router = src.api.client_routes.router

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
        "auth": "To access the API, use JWT authentication via '/api/v1/auth/login'",
    }
