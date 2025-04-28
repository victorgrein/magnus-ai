"""
Script to create example contacts for the demo client:
- Contacts with conversation history
- Different client profiles
- Fake data for demonstration
"""

import os
import sys
import logging
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
from src.models.models import Contact, User, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_demo_contacts():
    """Create example contacts for the demo client"""
    try:
        # Load environment variables
        load_dotenv()

        # Get database settings
        db_url = os.getenv("POSTGRES_CONNECTION_STRING")
        if not db_url:
            logger.error("Environment variable POSTGRES_CONNECTION_STRING not defined")
            return False

        # Connect to the database
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # Get demo client by user email
            demo_email = os.getenv("DEMO_EMAIL", "demo@example.com")
            demo_user = session.query(User).filter(User.email == demo_email).first()

            if not demo_user or not demo_user.client_id:
                logger.error(
                    f"Demo user not found or not associated with a client: {demo_email}"
                )
                return False

            client_id = demo_user.client_id

            # Check if there are already contacts for this client
            existing_contacts = (
                session.query(Contact).filter(Contact.client_id == client_id).all()
            )
            if existing_contacts:
                logger.info(
                    f"There are already {len(existing_contacts)} contacts for the client {client_id}"
                )
                return True

            # Example contact definitions
            contacts = [
                {
                    "name": "Maria Silva",
                    "ext_id": "5511999998888",
                    "meta": {
                        "source": "whatsapp",
                        "tags": ["cliente_vip", "suporte_premium"],
                        "location": "São Paulo, SP",
                        "last_contact": "2023-08-15T14:30:00Z",
                        "account_details": {
                            "customer_since": "2020-03-10",
                            "plan": "Enterprise",
                            "payment_status": "active",
                        },
                    },
                },
                {
                    "name": "João Santos",
                    "ext_id": "5511988887777",
                    "meta": {
                        "source": "whatsapp",
                        "tags": ["prospecção", "demo_solicitada"],
                        "location": "Rio de Janeiro, RJ",
                        "last_contact": "2023-09-20T10:15:00Z",
                        "interests": ["automação", "marketing", "chatbots"],
                    },
                },
                {
                    "name": "Ana Oliveira",
                    "ext_id": "5511977776666",
                    "meta": {
                        "source": "telegram",
                        "tags": ["suporte_técnico", "problema_resolvido"],
                        "location": "Belo Horizonte, MG",
                        "last_contact": "2023-09-25T16:45:00Z",
                        "support_cases": [
                            {
                                "id": "SUP-2023-1234",
                                "status": "closed",
                                "priority": "high",
                            },
                            {
                                "id": "SUP-2023-1567",
                                "status": "open",
                                "priority": "medium",
                            },
                        ],
                    },
                },
                {
                    "name": "Carlos Pereira",
                    "ext_id": "5511966665555",
                    "meta": {
                        "source": "whatsapp",
                        "tags": ["cancelamento", "retenção"],
                        "location": "Porto Alegre, RS",
                        "last_contact": "2023-09-10T09:30:00Z",
                        "account_details": {
                            "customer_since": "2019-05-22",
                            "plan": "Professional",
                            "payment_status": "overdue",
                            "invoice_pending": True,
                        },
                    },
                },
                {
                    "name": "Fernanda Lima",
                    "ext_id": "5511955554444",
                    "meta": {
                        "source": "telegram",
                        "tags": ["parceiro", "integrador"],
                        "location": "Curitiba, PR",
                        "last_contact": "2023-09-18T14:00:00Z",
                        "partner_details": {
                            "company": "TechSolutions Ltda",
                            "partner_level": "Gold",
                            "certified": True,
                        },
                    },
                },
            ]

            # Create the contacts
            for contact_data in contacts:
                contact = Contact(
                    client_id=client_id,
                    name=contact_data["name"],
                    ext_id=contact_data["ext_id"],
                    meta=contact_data["meta"],
                )

                session.add(contact)
                logger.info(
                    f"Contact '{contact_data['name']}' created for the client {client_id}"
                )

            session.commit()
            logger.info(
                f"All example contacts were created successfully for the client {client_id}"
            )
            return True

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(
                f"Database error when creating example contacts: {str(e)}"
            )
            return False

    except Exception as e:
        logger.error(f"Error when creating example contacts: {str(e)}")
        return False
    finally:
        session.close()


if __name__ == "__main__":
    success = create_demo_contacts()
    sys.exit(0 if success else 1)
