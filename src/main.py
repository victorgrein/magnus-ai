import os
import sys
from pathlib import Path

# Adiciona o diretório raiz ao PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from fastapi import FastAPI
from typing import Dict, Any
from src.config.database import engine, Base
from src.api.routes import router
from src.config.settings import settings
from src.utils.logger import setup_logger

# Configurar logger
logger = setup_logger(__name__)

# Inicialização do FastAPI
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
)

# Configuração do PostgreSQL
POSTGRES_CONNECTION_STRING = os.getenv(
    "POSTGRES_CONNECTION_STRING",
    "postgresql://postgres:root@localhost:5432/google-a2a-saas"
)

# Criar as tabelas no banco de dados
Base.metadata.create_all(bind=engine)

# Incluir as rotas
app.include_router(router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to A2A SaaS API"}
