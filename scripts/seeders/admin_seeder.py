"""
Script to create an initial admin user:
- Email: admin@evoai.com
- Password: defined in the ADMIN_INITIAL_PASSWORD environment variable
- is_admin: True
- is_active: True
- email_verified: True
"""

import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from src.models.models import User
from src.utils.security import get_password_hash

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_admin_user():
    """Create an initial admin user in the system"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Get database settings
        db_url = os.getenv("POSTGRES_CONNECTION_STRING")
        if not db_url:
            logger.error("Environment variable POSTGRES_CONNECTION_STRING not defined")
            return False
        
        # Get admin password
        admin_password = os.getenv("ADMIN_INITIAL_PASSWORD")
        if not admin_password:
            logger.error("Environment variable ADMIN_INITIAL_PASSWORD not defined")
            return False
            
        # Admin email configuration
        admin_email = os.getenv("ADMIN_EMAIL", "admin@evoai.com")
        
        # Connect to the database
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Verificar se o administrador já existe
        existing_admin = session.query(User).filter(User.email == admin_email).first()
        if existing_admin:
            logger.info(f"Admin with email {admin_email} already exists")
            return True
        
        # Create admin
        admin_user = User(
            email=admin_email,
            password_hash=get_password_hash(admin_password),
            is_admin=True,
            is_active=True,
            email_verified=True
        )
        
        # Add and commit
        session.add(admin_user)
        session.commit()
        
        logger.info(f"Admin created successfully: {admin_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating admin: {str(e)}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    success = create_admin_user()
    sys.exit(0 if success else 1) 