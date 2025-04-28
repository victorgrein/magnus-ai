"""
Script para criar ferramentas padrão:
- Pesquisa Web
- Consulta a Documentos
- Consulta a Base de Conhecimento
- Integração WhatsApp/Telegram
Cada uma com configurações básicas para demonstração
"""

import os
import sys
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
from src.models.models import Tool

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_tools():
    """Cria ferramentas padrão no sistema"""
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
            # Verificar se já existem ferramentas
            existing_tools = session.query(Tool).all()
            if existing_tools:
                logger.info(f"Já existem {len(existing_tools)} ferramentas cadastradas")
                return True
            
            # Definições das ferramentas
            tools = [
                {
                    "name": "web_search",
                    "description": "Pesquisa na web para obter informações atualizadas",
                    "config_json": {
                        "provider": "brave",
                        "api_base": "https://api.search.brave.com/res/v1/web/search",
                        "api_key_env": "BRAVE_API_KEY",
                        "max_results": 5,
                        "safe_search": "moderate"
                    },
                    "environments": {
                        "production": True,
                        "development": True,
                        "staging": True
                    }
                },
                {
                    "name": "document_query",
                    "description": "Consulta documentos internos para obter informações específicas",
                    "config_json": {
                        "provider": "internal",
                        "api_base": "${KNOWLEDGE_API_URL}/documents",
                        "api_key_env": "KNOWLEDGE_API_KEY",
                        "embeddings_model": "text-embedding-3-small",
                        "max_chunks": 10,
                        "similarity_threshold": 0.75
                    },
                    "environments": {
                        "production": True,
                        "development": True,
                        "staging": True
                    }
                },
                {
                    "name": "knowledge_base",
                    "description": "Consulta base de conhecimento para solução de problemas",
                    "config_json": {
                        "provider": "internal",
                        "api_base": "${KNOWLEDGE_API_URL}/kb",
                        "api_key_env": "KNOWLEDGE_API_KEY",
                        "max_results": 3,
                        "categories": ["support", "faq", "troubleshooting"]
                    },
                    "environments": {
                        "production": True,
                        "development": True,
                        "staging": True
                    }
                },
                {
                    "name": "whatsapp_integration",
                    "description": "Integração com WhatsApp para envio e recebimento de mensagens",
                    "config_json": {
                        "provider": "meta",
                        "api_base": "https://graph.facebook.com/v17.0",
                        "api_key_env": "WHATSAPP_API_KEY",
                        "phone_number_id": "${WHATSAPP_PHONE_ID}",
                        "webhook_verify_token": "${WHATSAPP_VERIFY_TOKEN}",
                        "templates_enabled": True
                    },
                    "environments": {
                        "production": True,
                        "development": False,
                        "staging": True
                    }
                },
                {
                    "name": "telegram_integration",
                    "description": "Integração com Telegram para envio e recebimento de mensagens",
                    "config_json": {
                        "provider": "telegram",
                        "api_base": "https://api.telegram.org",
                        "api_key_env": "TELEGRAM_BOT_TOKEN",
                        "webhook_url": "${APP_URL}/webhook/telegram",
                        "allowed_updates": ["message", "callback_query"]
                    },
                    "environments": {
                        "production": True,
                        "development": False,
                        "staging": True
                    }
                }
            ]
            
            # Criar as ferramentas
            for tool_data in tools:
                # Substituir placeholders por variáveis de ambiente quando disponíveis
                if "api_base" in tool_data["config_json"]:
                    if "${KNOWLEDGE_API_URL}" in tool_data["config_json"]["api_base"]:
                        tool_data["config_json"]["api_base"] = tool_data["config_json"]["api_base"].replace(
                            "${KNOWLEDGE_API_URL}", os.getenv("KNOWLEDGE_API_URL", "http://localhost:5540")
                        )
                
                if "webhook_url" in tool_data["config_json"]:
                    if "${APP_URL}" in tool_data["config_json"]["webhook_url"]:
                        tool_data["config_json"]["webhook_url"] = tool_data["config_json"]["webhook_url"].replace(
                            "${APP_URL}", os.getenv("APP_URL", "http://localhost:8000")
                        )
                
                if "phone_number_id" in tool_data["config_json"]:
                    if "${WHATSAPP_PHONE_ID}" in tool_data["config_json"]["phone_number_id"]:
                        tool_data["config_json"]["phone_number_id"] = os.getenv("WHATSAPP_PHONE_ID", "")
                
                if "webhook_verify_token" in tool_data["config_json"]:
                    if "${WHATSAPP_VERIFY_TOKEN}" in tool_data["config_json"]["webhook_verify_token"]:
                        tool_data["config_json"]["webhook_verify_token"] = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
                
                tool = Tool(
                    name=tool_data["name"],
                    description=tool_data["description"],
                    config_json=tool_data["config_json"],
                    environments=tool_data["environments"]
                )
                
                session.add(tool)
                logger.info(f"Ferramenta '{tool_data['name']}' criada com sucesso")
            
            session.commit()
            logger.info("Todas as ferramentas foram criadas com sucesso")
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro de banco de dados ao criar ferramentas: {str(e)}")
            return False
        
    except Exception as e:
        logger.error(f"Erro ao criar ferramentas: {str(e)}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    success = create_tools()
    sys.exit(0 if success else 1) 