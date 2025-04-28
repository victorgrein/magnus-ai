import os
from typing import Optional, List
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
    
    # Configurações JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_TIME: int = int(os.getenv("JWT_EXPIRATION_TIME", 30))
    
    # Configurações SendGrid
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@yourdomain.com")
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8000")
    
    # Configurações do Servidor
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Configurações de CORS
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # Configurações de Token
    TOKEN_EXPIRY_HOURS: int = int(os.getenv("TOKEN_EXPIRY_HOURS", 24))  # Tokens de verificação/reset
    
    # Configurações de Segurança
    PASSWORD_MIN_LENGTH: int = int(os.getenv("PASSWORD_MIN_LENGTH", 8))
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", 5))
    LOGIN_LOCKOUT_MINUTES: int = int(os.getenv("LOGIN_LOCKOUT_MINUTES", 30))
    
    # Configurações de Seeders
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@evoai.com")
    ADMIN_INITIAL_PASSWORD: str = os.getenv("ADMIN_INITIAL_PASSWORD", "senhaforte123")
    DEMO_EMAIL: str = os.getenv("DEMO_EMAIL", "demo@exemplo.com")
    DEMO_PASSWORD: str = os.getenv("DEMO_PASSWORD", "demo123")
    DEMO_CLIENT_NAME: str = os.getenv("DEMO_CLIENT_NAME", "Cliente Demo")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings() 