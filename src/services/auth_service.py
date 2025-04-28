from sqlalchemy.orm import Session
from src.models.models import User
from src.schemas.user import TokenData
from src.services.user_service import authenticate_user, get_user_by_email
from src.utils.security import create_jwt_token
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from src.config.settings import settings
from src.config.database import get_db
from datetime import datetime, timedelta
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Definir scheme de autenticação OAuth2 com password flow
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Obtém o usuário atual a partir do token JWT
    
    Args:
        token: Token JWT
        db: Sessão do banco de dados
        
    Returns:
        User: Usuário atual
        
    Raises:
        HTTPException: Se o token for inválido ou o usuário não for encontrado
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decodificar o token
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Extrair dados do token
        email: str = payload.get("sub")
        if email is None:
            logger.warning("Token sem email (sub)")
            raise credentials_exception
        
        # Verificar se o token expirou
        exp = payload.get("exp")
        if exp is None or datetime.fromtimestamp(exp) < datetime.utcnow():
            logger.warning(f"Token expirado para {email}")
            raise credentials_exception
        
        # Criar objeto TokenData
        token_data = TokenData(
            sub=email,
            exp=datetime.fromtimestamp(exp),
            is_admin=payload.get("is_admin", False),
            client_id=payload.get("client_id")
        )
        
    except JWTError as e:
        logger.error(f"Erro ao decodificar token JWT: {str(e)}")
        raise credentials_exception
    
    # Buscar usuário no banco de dados
    user = get_user_by_email(db, email=token_data.sub)
    if user is None:
        logger.warning(f"Usuário não encontrado para o email: {token_data.sub}")
        raise credentials_exception
    
    if not user.is_active:
        logger.warning(f"Tentativa de acesso com usuário inativo: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )
    
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Verifica se o usuário atual está ativo
    
    Args:
        current_user: Usuário atual
        
    Returns:
        User: Usuário atual se estiver ativo
        
    Raises:
        HTTPException: Se o usuário não estiver ativo
    """
    if not current_user.is_active:
        logger.warning(f"Tentativa de acesso com usuário inativo: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )
    return current_user

async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Verifica se o usuário atual é um administrador
    
    Args:
        current_user: Usuário atual
        
    Returns:
        User: Usuário atual se for administrador
        
    Raises:
        HTTPException: Se o usuário não for administrador
    """
    if not current_user.is_admin:
        logger.warning(f"Tentativa de acesso admin por usuário não-admin: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão negada. Acesso restrito a administradores."
        )
    return current_user

def create_access_token(user: User) -> str:
    """
    Cria um token de acesso JWT para o usuário
    
    Args:
        user: Usuário para o qual criar o token
        
    Returns:
        str: Token JWT
    """
    # Dados a serem incluídos no token
    token_data = {
        "sub": user.email,
        "is_admin": user.is_admin,
    }
    
    # Incluir client_id apenas se não for administrador
    if not user.is_admin and user.client_id:
        token_data["client_id"] = str(user.client_id)
    
    # Criar token
    return create_jwt_token(token_data) 