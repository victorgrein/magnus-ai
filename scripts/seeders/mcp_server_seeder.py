"""
Script para criar servidores MCP padrão:
- Servidor Anthropic Claude
- Servidor OpenAI GPT
- Servidor Google Gemini
- Servidor Ollama (local)
Cada um com configurações padrão para produção
"""

import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
from src.models.models import MCPServer

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_mcp_servers():
    """Cria servidores MCP padrão no sistema"""
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
            # Verificar se já existem servidores MCP
            existing_servers = session.query(MCPServer).all()
            if existing_servers:
                logger.info(f"Já existem {len(existing_servers)} servidores MCP cadastrados")
                return True
            
            # Definições dos servidores MCP
            mcp_servers = [
                {
                    "name": "Anthropic Claude",
                    "description": "Servidor para modelos Claude da Anthropic",
                    "config_json": {
                        "provider": "anthropic",
                        "models": ["claude-3-sonnet-20240229", "claude-3-opus-20240229", "claude-3-haiku-20240307"],
                        "api_base": "https://api.anthropic.com/v1",
                        "api_key_env": "ANTHROPIC_API_KEY"
                    },
                    "environments": {
                        "production": True,
                        "development": True,
                        "staging": True
                    },
                    "tools": ["function_calling", "web_search"],
                    "type": "official"
                },
                {
                    "name": "OpenAI GPT",
                    "description": "Servidor para modelos GPT da OpenAI",
                    "config_json": {
                        "provider": "openai",
                        "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
                        "api_base": "https://api.openai.com/v1",
                        "api_key_env": "OPENAI_API_KEY"
                    },
                    "environments": {
                        "production": True,
                        "development": True,
                        "staging": True
                    },
                    "tools": ["function_calling", "web_search", "image_generation"],
                    "type": "official"
                },
                {
                    "name": "Google Gemini",
                    "description": "Servidor para modelos Gemini do Google",
                    "config_json": {
                        "provider": "google",
                        "models": ["gemini-pro", "gemini-ultra"],
                        "api_base": "https://generativelanguage.googleapis.com/v1",
                        "api_key_env": "GOOGLE_API_KEY"
                    },
                    "environments": {
                        "production": True,
                        "development": True,
                        "staging": True
                    },
                    "tools": ["function_calling", "web_search"],
                    "type": "official"
                },
                {
                    "name": "Ollama Local",
                    "description": "Servidor para modelos locais via Ollama",
                    "config_json": {
                        "provider": "ollama",
                        "models": ["llama3", "mistral", "mixtral"],
                        "api_base": "http://localhost:11434",
                        "api_key_env": None
                    },
                    "environments": {
                        "production": False,
                        "development": True,
                        "staging": False
                    },
                    "tools": [],
                    "type": "community"
                }
            ]
            
            # Criar os servidores MCP
            for server_data in mcp_servers:
                server = MCPServer(
                    name=server_data["name"],
                    description=server_data["description"],
                    config_json=server_data["config_json"],
                    environments=server_data["environments"],
                    tools=server_data["tools"],
                    type=server_data["type"]
                )
                
                session.add(server)
                logger.info(f"Servidor MCP '{server_data['name']}' criado com sucesso")
            
            session.commit()
            logger.info("Todos os servidores MCP foram criados com sucesso")
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro de banco de dados ao criar servidores MCP: {str(e)}")
            return False
        
    except Exception as e:
        logger.error(f"Erro ao criar servidores MCP: {str(e)}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    success = create_mcp_servers()
    sys.exit(0 if success else 1) 