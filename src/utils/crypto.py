from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

# Get the secret key from the .env or generate one
SECRET_KEY = os.getenv("ENCRYPTION_KEY")
if not SECRET_KEY:
    SECRET_KEY = Fernet.generate_key().decode()
    logger.warning(f"ENCRYPTION_KEY missing from .env. Generated: {SECRET_KEY}")

# Create the Fernet object with the key
fernet = Fernet(SECRET_KEY.encode() if isinstance(SECRET_KEY, str) else SECRET_KEY)


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key before saving in the database"""
    if not api_key:
        return ""
    try:
        return fernet.encrypt(api_key.encode()).decode()
    except Exception as e:
        logger.error(f"Error encrypting API key: {str(e)}")
        raise


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key for use"""
    if not encrypted_key:
        return ""
    try:
        return fernet.decrypt(encrypted_key.encode()).decode()
    except Exception as e:
        logger.error(f"Error decrypting API key: {str(e)}")
        raise
