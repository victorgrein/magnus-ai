"""
Script para criar um usuário administrador inicial:
- Email: admin@evoai.com
- Senha: definida nas variáveis de ambiente ADMIN_INITIAL_PASSWORD
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
    """Cria um usuário administrador inicial no sistema"""
    try:
        # Carregar variáveis de ambiente
        load_dotenv()
        
        # Obter configurações do banco de dados
        db_url = os.getenv("POSTGRES_CONNECTION_STRING")
        if not db_url:
            logger.error("Variável de ambiente POSTGRES_CONNECTION_STRING não definida")
            return False
        
        # Obter senha do administrador
        admin_password = os.getenv("ADMIN_INITIAL_PASSWORD")
        if not admin_password:
            logger.error("Variável de ambiente ADMIN_INITIAL_PASSWORD não definida")
            return False
            
        # Configuração do email do admin
        admin_email = os.getenv("ADMIN_EMAIL", "admin@evoai.com")
        
        # Conectar ao banco de dados
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Verificar se o administrador já existe
        existing_admin = session.query(User).filter(User.email == admin_email).first()
        if existing_admin:
            logger.info(f"Administrador com email {admin_email} já existe")
            return True
        
        # Criar administrador
        admin_user = User(
            email=admin_email,
            password_hash=get_password_hash(admin_password),
            is_admin=True,
            is_active=True,
            email_verified=True
        )
        
        # Adicionar e comitar
        session.add(admin_user)
        session.commit()
        
        logger.info(f"Administrador criado com sucesso: {admin_email}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao criar administrador: {str(e)}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    success = create_admin_user()
    sys.exit(0 if success else 1) 