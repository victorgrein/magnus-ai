"""
Script para criar um cliente de exemplo:
- Nome: Cliente Demo
- Com usuário associado:
  - Email: demo@exemplo.com
  - Senha: demo123 (ou definida em variável de ambiente)
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_demo_client_and_user():
    """Cria um cliente e usuário de demonstração no sistema"""
    try:
        # Carregar variáveis de ambiente
        load_dotenv()
        
        # Obter configurações do banco de dados
        db_url = os.getenv("POSTGRES_CONNECTION_STRING")
        if not db_url:
            logger.error("Variável de ambiente POSTGRES_CONNECTION_STRING não definida")
            return False
        
        # Obter senha do usuário demo (ou usar padrão)
        demo_password = os.getenv("DEMO_PASSWORD", "demo123")
        
        # Configurações do cliente e usuário demo
        demo_client_name = os.getenv("DEMO_CLIENT_NAME", "Cliente Demo")
        demo_email = os.getenv("DEMO_EMAIL", "demo@exemplo.com")
        
        # Conectar ao banco de dados
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # Verificar se o usuário já existe
            existing_user = session.query(User).filter(User.email == demo_email).first()
            if existing_user:
                logger.info(f"Usuário demo com email {demo_email} já existe")
                return True
            
            # Criar cliente demo
            demo_client = Client(name=demo_client_name)
            session.add(demo_client)
            session.flush()  # Obter o ID do cliente
            
            # Criar usuário demo associado ao cliente
            demo_user = User(
                email=demo_email,
                password_hash=get_password_hash(demo_password),
                client_id=demo_client.id,
                is_admin=False,
                is_active=True,
                email_verified=True
            )
            
            # Adicionar e comitar
            session.add(demo_user)
            session.commit()
            
            logger.info(f"Cliente demo '{demo_client_name}' criado com sucesso")
            logger.info(f"Usuário demo criado com sucesso: {demo_email}")
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro de banco de dados ao criar cliente/usuário demo: {str(e)}")
            return False
        
    except Exception as e:
        logger.error(f"Erro ao criar cliente/usuário demo: {str(e)}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    success = create_demo_client_and_user()
    sys.exit(0 if success else 1) 