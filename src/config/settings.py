import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Configurações do projeto"""
    
    # Configurações da API
    API_TITLE: str = "Agent Runner API"
    API_DESCRIPTION: str = "API para execução de agentes de IA"
    API_VERSION: str = "1.0.0"
    
    # Configurações do banco de dados
    POSTGRES_CONNECTION_STRING: str = os.getenv(
        "POSTGRES_CONNECTION_STRING",
        "postgresql://postgres:root@localhost:5432/google-a2a-saas"
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
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Instância global das configurações
settings = Settings() 