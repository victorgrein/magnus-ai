from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets
import string
from jose import jwt
from src.config.settings import settings
import logging
import bcrypt
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Corrigir erro do bcrypt com passlib
if not hasattr(bcrypt, '__about__'):
    @dataclass
    class BcryptAbout:
        __version__: str = getattr(bcrypt, "__version__")
    
    setattr(bcrypt, "__about__", BcryptAbout())

# Contexto para hash de senhas usando bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Cria um hash da senha fornecida"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha fornecida corresponde ao hash armazenado"""
    return pwd_context.verify(plain_password, hashed_password)

def create_jwt_token(data: dict, expires_delta: timedelta = None) -> str:
    """Cria um token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.JWT_EXPIRATION_TIME
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt

def generate_token(length: int = 32) -> str:
    """Gera um token seguro para verificação de email ou reset de senha"""
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for _ in range(length))
    return token 