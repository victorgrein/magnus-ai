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
            tools = []
            
            # Criar as ferramentas
            for tool_data in tools:
                
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