import os
import sys
from pathlib import Path

# Adiciona o diretório raiz ao PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from src.config.database import engine, Base
from src.api.routes import router
from src.api.auth_routes import router as auth_router
from src.api.admin_routes import router as admin_router
from src.config.settings import settings
from src.utils.logger import setup_logger

# Configurar logger
logger = setup_logger(__name__)

# Inicialização do FastAPI
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION + """
    \n\n
    ## Autenticação
    Esta API utiliza autenticação JWT (JSON Web Token). Para acessar os endpoints protegidos:
    
    1. Registre-se em `/api/v1/auth/register` ou faça login em `/api/v1/auth/login`
    2. Use o token recebido no header de autorização: `Authorization: Bearer {token}`
    3. Tokens expiram após o tempo configurado (padrão: 30 minutos)
    
    Diferente da versão anterior que usava API Key, o sistema JWT:
    - Identifica o usuário específico que está fazendo a requisição
    - Limita o acesso apenas aos recursos do cliente ao qual o usuário está associado
    - Distingue entre usuários comuns e administradores para controle de acesso
    
    ## Área Administrativa
    Funcionalidades exclusivas para administradores estão disponíveis em `/api/v1/admin/*`:
    
    - Gerenciamento de usuários administradores
    - Logs de auditoria para rastreamento de ações
    - Controle de acesso privilegiado
    
    Essas rotas são acessíveis apenas para usuários com flag `is_admin=true`.
    """,
    version=settings.API_VERSION,
)

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração do PostgreSQL
POSTGRES_CONNECTION_STRING = os.getenv(
    "POSTGRES_CONNECTION_STRING",
    "postgresql://postgres:root@localhost:5432/evo_ai"
)

# Criar as tabelas no banco de dados
Base.metadata.create_all(bind=engine)

# Incluir as rotas
app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {
        "message": "Bem-vindo à API Evo AI",
        "documentation": "/docs",
        "version": settings.API_VERSION,
        "auth": "Para acessar a API, use autenticação JWT via '/api/v1/auth/login'"
    }
