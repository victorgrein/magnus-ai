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

# Fix bcrypt error with passlib
if not hasattr(bcrypt, "__about__"):

    @dataclass
    class BcryptAbout:
        __version__: str = getattr(bcrypt, "__version__")

    setattr(bcrypt, "__about__", BcryptAbout())

# Context for password hashing using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Creates a password hash"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies if the provided password matches the stored hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_jwt_token(data: dict, expires_delta: timedelta = None) -> str:
    """Creates a JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRATION_TIME)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def generate_token(length: int = 32) -> str:
    """Generates a secure token for email verification or password reset"""
    alphabet = string.ascii_letters + string.digits
    token = "".join(secrets.choice(alphabet) for _ in range(length))
    return token
