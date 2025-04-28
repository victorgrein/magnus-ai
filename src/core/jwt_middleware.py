from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from src.config.settings import settings
from datetime import datetime
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models.models import User
from src.services.user_service import get_user_by_email
from uuid import UUID
import logging
from typing import Optional

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_jwt_token(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Extrai e valida o token JWT
    
    Args:
        token: Token JWT
        
    Returns:
        dict: Dados do payload do token
        
    Raises:
        HTTPException: Se o token for inválido
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        email: str = payload.get("sub")
        if email is None:
            logger.warning("Token sem email (sub)")
            raise credentials_exception
        
        exp = payload.get("exp")
        if exp is None or datetime.fromtimestamp(exp) < datetime.utcnow():
            logger.warning(f"Token expirado para {email}")
            raise credentials_exception
        
        return payload
        
    except JWTError as e:
        logger.error(f"Erro ao decodificar token JWT: {str(e)}")
        raise credentials_exception

async def verify_user_client(
    payload: dict = Depends(get_jwt_token),
    db: Session = Depends(get_db),
    required_client_id: UUID = None
) -> bool:
    """
    Verifica se o usuário está associado ao cliente especificado
    
    Args:
        payload: Payload do token JWT
        db: Sessão do banco de dados
        required_client_id: ID do cliente que deve ser verificado
        
    Returns:
        bool: True se verificado com sucesso
        
    Raises:
        HTTPException: Se o usuário não tiver permissão
    """
    # Administradores têm acesso a todos os clientes
    if payload.get("is_admin", False):
        return True
    
    # Para não-admins, verificar se o client_id corresponde
    user_client_id = payload.get("client_id")
    if not user_client_id:
        logger.warning(f"Usuário não-admin sem client_id no token: {payload.get('sub')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário não associado a um cliente"
        )
    
    # Se não foi especificado um client_id para verificar, qualquer cliente é válido
    if not required_client_id:
        return True
    
    # Verificar se o client_id do usuário corresponde ao required_client_id
    if str(user_client_id) != str(required_client_id):
        logger.warning(f"Acesso negado: Usuário {payload.get('sub')} tentou acessar recursos do cliente {required_client_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão negada para acessar recursos deste cliente"
        )
    
    return True

async def verify_admin(payload: dict = Depends(get_jwt_token)) -> bool:
    """
    Verifica se o usuário é um administrador
    
    Args:
        payload: Payload do token JWT
        
    Returns:
        bool: True se for administrador
        
    Raises:
        HTTPException: Se o usuário não for administrador
    """
    if not payload.get("is_admin", False):
        logger.warning(f"Acesso admin negado para usuário: {payload.get('sub')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão negada. Acesso restrito a administradores."
        )
    
    return True

def get_current_user_client_id(payload: dict = Depends(get_jwt_token)) -> Optional[UUID]:
    """
    Obtém o ID do cliente associado ao usuário atual
    
    Args:
        payload: Payload do token JWT
        
    Returns:
        Optional[UUID]: ID do cliente ou None se for administrador
    """
    if payload.get("is_admin", False):
        return None
    
    client_id = payload.get("client_id")
    if client_id:
        return UUID(client_id)
    
    return None 