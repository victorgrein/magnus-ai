from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from src.config.settings import settings
import logging

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

async def get_api_key(api_key_header: str = Security(api_key_header)) -> str:
    """Verifica se a API Key fornecida é válida"""
    try:
        if api_key_header == settings.API_KEY:
            return api_key_header
        else:
            logger.warning(f"Tentativa de acesso com API Key inválida: {api_key_header}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key inválida"
            )
    except Exception as e:
        logger.error(f"Erro ao verificar API Key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Erro ao verificar API Key"
        ) 