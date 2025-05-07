"""
Script to create a demo client:
- Name: Demo Client
- With associated user:
  - Email: demo@example.com
  - Password: demo123 (or defined in environment variable)
  - is_admin: False
  - is_active: True
  - email_verified: True
"""

import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
from src.models.models import User, Client
from src.utils.security import get_password_hash

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_demo_client_and_user():
    """Create a demo client and user in the system"""
    try:
        # Load environment variables
        load_dotenv()

        # Get database settings
        db_url = os.getenv("POSTGRES_CONNECTION_STRING")
        if not db_url:
            logger.error("Environment variable POSTGRES_CONNECTION_STRING not defined")
            return False

        # Get demo user password (or use default)
        demo_password = os.getenv("DEMO_PASSWORD", "demo123")

        # Demo client and user settings
        demo_client_name = os.getenv("DEMO_CLIENT_NAME", "Demo Client")
        demo_email = os.getenv("DEMO_EMAIL", "demo@example.com")

        # Connect to the database
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # Check if the user already exists
            existing_user = session.query(User).filter(User.email == demo_email).first()
            if existing_user:
                logger.info(f"Demo user with email {demo_email} already exists")
                return True

            # Create demo client
            demo_client = Client(name=demo_client_name, email=demo_email)
            session.add(demo_client)
            session.flush()  # Get the client ID

            # Create demo user associated with the client
            demo_user = User(
                email=demo_email,
                password_hash=get_password_hash(demo_password),
                client_id=demo_client.id,
                is_admin=False,
                is_active=True,
                email_verified=True,
            )

            # Add and commit
            session.add(demo_user)
            session.commit()

            logger.info(f"Demo client '{demo_client_name}' created successfully")
            logger.info(f"Demo user created successfully: {demo_email}")
            return True

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error when creating demo client/user: {str(e)}")
            return False

    except Exception as e:
        logger.error(f"Error when creating demo client/user: {str(e)}")
        return False
    finally:
        session.close()


if __name__ == "__main__":
    success = create_demo_client_and_user()
    sys.exit(0 if success else 1)
