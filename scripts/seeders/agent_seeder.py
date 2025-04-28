"""
Script para criar agentes de exemplo para o cliente demo:
- Agente Atendimento: configurado para responder perguntas gerais
- Agente Vendas: configurado para responder sobre produtos
- Agente FAQ: configurado para responder perguntas frequentes
Cada agente com instruções e configurações pré-definidas
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
    """Cria agentes de exemplo para o cliente demo"""
    try:
        # Carregar variáveis de ambiente
        load_dotenv()
        
        # Obter configurações do banco de dados
        db_url = os.getenv("POSTGRES_CONNECTION_STRING")
        if not db_url:
            logger.error("Variável de ambiente POSTGRES_CONNECTION_STRING não definida")
            return False
        
        # Conectar ao banco de dados
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # Obter o cliente demo pelo email do usuário
            demo_email = os.getenv("DEMO_EMAIL", "demo@exemplo.com")
            demo_user = session.query(User).filter(User.email == demo_email).first()
            
            if not demo_user or not demo_user.client_id:
                logger.error(f"Usuário demo não encontrado ou não associado a um cliente: {demo_email}")
                return False
                
            client_id = demo_user.client_id
            
            # Verificar se já existem agentes para este cliente
            existing_agents = session.query(Agent).filter(Agent.client_id == client_id).all()
            if existing_agents:
                logger.info(f"Já existem {len(existing_agents)} agentes para o cliente {client_id}")
                return True
            
            # Definições dos agentes de exemplo
            agents = [
                {
                    "name": "Atendimento_Geral",
                    "description": "Agente para atendimento geral e dúvidas básicas",
                    "type": "llm",
                    "model": "gpt-3.5-turbo",
                    "api_key": "${OPENAI_API_KEY}",  # Será substituído pela variável de ambiente
                    "instruction": """
                        Você é um assistente de atendimento ao cliente da empresa. 
                        Seja cordial, objetivo e eficiente. Responda às dúvidas dos clientes
                        de forma clara e sucinta. Se não souber a resposta, informe que irá
                        consultar um especialista e retornará em breve.
                    """,
                    "config": {
                        "temperature": 0.7,
                        "max_tokens": 500,
                        "tools": []
                    }
                },
                {
                    "name": "Vendas_Produtos",
                    "description": "Agente especializado em vendas e informações sobre produtos",
                    "type": "llm",
                    "model": "claude-3-sonnet-20240229",
                    "api_key": "${ANTHROPIC_API_KEY}",  # Será substituído pela variável de ambiente
                    "instruction": """
                        Você é um especialista em vendas da empresa. 
                        Seu objetivo é fornecer informações detalhadas sobre produtos,
                        comparar diferentes opções, destacar benefícios e vantagens competitivas.
                        Use uma linguagem persuasiva mas honesta, e sempre busque entender
                        as necessidades do cliente antes de recomendar um produto.
                    """,
                    "config": {
                        "temperature": 0.8,
                        "max_tokens": 800,
                        "tools": ["web_search"]
                    }
                },
                {
                    "name": "FAQ_Bot",
                    "description": "Agente para responder perguntas frequentes",
                    "type": "llm",
                    "model": "gemini-pro",
                    "api_key": "${GOOGLE_API_KEY}",  # Será substituído pela variável de ambiente
                    "instruction": """
                        Você é um assistente especializado em responder perguntas frequentes.
                        Suas respostas devem ser diretas, objetivas e baseadas nas informações
                        da empresa. Utilize uma linguagem simples e acessível. Se a pergunta
                        não estiver relacionada às FAQs disponíveis, direcione o cliente para
                        o canal de atendimento adequado.
                    """,
                    "config": {
                        "temperature": 0.5,
                        "max_tokens": 400,
                        "tools": []
                    }
                }
            ]
            
            # Criar os agentes
            for agent_data in agents:
                # Substituir placeholders de API Keys por variáveis de ambiente quando disponíveis
                if "${OPENAI_API_KEY}" in agent_data["api_key"]:
                    agent_data["api_key"] = os.getenv("OPENAI_API_KEY", "")
                elif "${ANTHROPIC_API_KEY}" in agent_data["api_key"]:
                    agent_data["api_key"] = os.getenv("ANTHROPIC_API_KEY", "")
                elif "${GOOGLE_API_KEY}" in agent_data["api_key"]:
                    agent_data["api_key"] = os.getenv("GOOGLE_API_KEY", "")
                
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
                logger.info(f"Agente '{agent_data['name']}' criado para o cliente {client_id}")
            
            session.commit()
            logger.info(f"Todos os agentes de exemplo foram criados com sucesso para o cliente {client_id}")
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro de banco de dados ao criar agentes de exemplo: {str(e)}")
            return False
        
    except Exception as e:
        logger.error(f"Erro ao criar agentes de exemplo: {str(e)}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    success = create_demo_agents()
    sys.exit(0 if success else 1) 