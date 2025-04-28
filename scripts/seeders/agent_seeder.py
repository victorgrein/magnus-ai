"""
Script to create example agents for the demo client:
- Agent Support: configured to answer general questions
- Agent Sales: configured to answer about products
- Agent FAQ: configured to answer frequently asked questions
Each agent with pre-defined instructions and configurations
"""

import os
import sys
import logging
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
from src.models.models import Agent, Client, User

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_demo_agents():
    """Create example agents for the demo client"""
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
            # Obter o cliente demo pelo email do usuário
            demo_email = os.getenv("DEMO_EMAIL", "demo@exemplo.com")
            demo_user = session.query(User).filter(User.email == demo_email).first()
            
            if not demo_user or not demo_user.client_id:
                logger.error(f"Demo user not found or not associated with a client: {demo_email}")
                return False
                
            client_id = demo_user.client_id
            
            # Verificar se já existem agentes para este cliente
            existing_agents = session.query(Agent).filter(Agent.client_id == client_id).all()
            if existing_agents:
                logger.info(f"There are already {len(existing_agents)} agents for the client {client_id}")
                return True
            
            # Example agent definitions
            agents = [
                {
                    "name": "Support_Agent",
                    "description": "Agent for general support and basic questions",
                    "type": "llm",
                    "model": "gpt-4.1-nano",
                    "api_key": "your-api-key-here",
                    "instruction": """
                        You are a customer support agent. 
                        Be friendly, objective and efficient. Answer customer questions
                        in a clear and concise manner. If you don't know the answer,
                        inform that you will consult a specialist and return soon.
                    """,
                    "config": {
                        "tools": [],
                        "mcp_servers": [],
                        "custom_tools": [],
                        "sub_agents": []
                    }
                },
                {
                    "name": "Sales_Products",
                    "description": "Specialized agent in sales and information about products",
                    "type": "llm",
                    "model": "gpt-4.1-nano",
                    "api_key": "your-api-key-here",
                    "instruction": """
                        You are a sales specialist. 
                        Your goal is to provide detailed information about products,
                        compare different options, highlight benefits and competitive advantages.
                        Use a persuasive but honest language, and always seek to understand
                        the customer's needs before recommending a product.
                    """,
                    "config": {
                        "tools": [],
                        "mcp_servers": [],
                        "custom_tools": [],
                        "sub_agents": []
                    }
                },
                {
                    "name": "FAQ_Bot",
                    "description": "Agent for answering frequently asked questions",
                    "type": "llm",
                    "model": "gpt-4.1-nano",
                    "api_key": "your-api-key-here",
                    "instruction": """
                        You are a specialized agent for answering frequently asked questions.
                        Your answers should be direct, objective and based on the information
                        of the company. Use a simple and accessible language. If the question
                        is not related to the available FAQs, redirect the client to the
                        appropriate support channel.
                    """,
                    "config": {
                        "tools": [],
                        "mcp_servers": [],
                        "custom_tools": [],
                        "sub_agents": []
                    }
                }
            ]
            
            # Create the agents
            for agent_data in agents:
                # Create the agent
                agent = Agent(
                    client_id=client_id,
                    name=agent_data["name"],
                    description=agent_data["description"],
                    type=agent_data["type"],
                    model=agent_data["model"],
                    api_key=agent_data["api_key"],
                    instruction=agent_data["instruction"].strip(),
                    config=agent_data["config"]
                )
                
                session.add(agent)
                logger.info(f"Agent '{agent_data['name']}' created for the client {client_id}")
            
            session.commit()
            logger.info(f"All example agents were created successfully for the client {client_id}")
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error when creating example agents: {str(e)}")
            return False
        
    except Exception as e:
        logger.error(f"Error when creating example agents: {str(e)}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    success = create_demo_agents()
    sys.exit(0 if success else 1) 