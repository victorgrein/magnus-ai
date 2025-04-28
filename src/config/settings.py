import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache
import secrets

class Settings(BaseSettings):
    """Configurações do projeto"""
    
    # Configurações da API
    API_TITLE: str = "Agent Runner API"
    API_DESCRIPTION: str = "API para execução de agentes de IA"
    API_VERSION: str = "1.0.0"
    
    # Configurações do banco de dados
    POSTGRES_CONNECTION_STRING: str = os.getenv(
        "POSTGRES_CONNECTION_STRING",
        "postgresql://postgres:root@localhost:5432/evo_ai"
    )
    
    # Configurações do OpenAI
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    
    # Configurações da aplicação
    APP_NAME: str = "app"
    USER_ID: str = "user_1"
    SESSION_ID: str = "session_001"
    
    # Configurações de logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: str = "logs"
    
    # Configurações da API de Conhecimento
    KNOWLEDGE_API_URL: str = os.getenv("KNOWLEDGE_API_URL", "http://localhost:5540")
    KNOWLEDGE_API_KEY: str = os.getenv("KNOWLEDGE_API_KEY", "")
    TENANT_ID: str = os.getenv("TENANT_ID", "")
    
    # Configurações do Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    
    # TTL do cache de ferramentas em segundos (1 hora)
    TOOLS_CACHE_TTL: int = int(os.getenv("TOOLS_CACHE_TTL", 3600))
    
    # Configurações da API
    API_KEY: str = secrets.token_urlsafe(32)  # Gera uma API Key aleatória se não for definida
    API_KEY_HEADER: str = "X-API-Key"
    
    # Configurações do Servidor
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings() 