from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from src.models.models import Client
from src.schemas.schemas import ClientCreate
from src.schemas.user import UserCreate
from src.services.user_service import create_user
from typing import List, Optional, Tuple
import uuid
import logging

logger = logging.getLogger(__name__)

def get_client(db: Session, client_id: uuid.UUID) -> Optional[Client]:
    """Busca um cliente pelo ID"""
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.warning(f"Cliente não encontrado: {client_id}")
            return None
        return client
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar cliente {client_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar cliente"
        )

def get_clients(db: Session, skip: int = 0, limit: int = 100) -> List[Client]:
    """Busca todos os clientes com paginação"""
    try:
        return db.query(Client).offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar clientes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar clientes"
        )

def create_client(db: Session, client: ClientCreate) -> Client:
    """Cria um novo cliente"""
    try:
        db_client = Client(**client.model_dump())
        db.add(db_client)
        db.commit()
        db.refresh(db_client)
        logger.info(f"Cliente criado com sucesso: {db_client.id}")
        return db_client
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao criar cliente: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar cliente"
        )

def update_client(db: Session, client_id: uuid.UUID, client: ClientCreate) -> Optional[Client]:
    """Atualiza um cliente existente"""
    try:
        db_client = get_client(db, client_id)
        if not db_client:
            return None
            
        for key, value in client.model_dump().items():
            setattr(db_client, key, value)
            
        db.commit()
        db.refresh(db_client)
        logger.info(f"Cliente atualizado com sucesso: {client_id}")
        return db_client
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao atualizar cliente {client_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar cliente"
        )

def delete_client(db: Session, client_id: uuid.UUID) -> bool:
    """Remove um cliente"""
    try:
        db_client = get_client(db, client_id)
        if not db_client:
            return False
            
        db.delete(db_client)
        db.commit()
        logger.info(f"Cliente removido com sucesso: {client_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao remover cliente {client_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover cliente"
        )

def create_client_with_user(db: Session, client_data: ClientCreate, user_data: UserCreate) -> Tuple[Optional[Client], str]:
    """
    Cria um novo cliente com um usuário associado
    
    Args:
        db: Sessão do banco de dados
        client_data: Dados do cliente a ser criado
        user_data: Dados do usuário a ser criado
        
    Returns:
        Tuple[Optional[Client], str]: Tupla com o cliente criado (ou None em caso de erro) e mensagem de status
    """
    try:
        # Iniciar transação - primeiro cria o cliente
        client = Client(**client_data.model_dump())
        db.add(client)
        db.flush()  # Obter o ID do cliente sem confirmar a transação
        
        # Usar o ID do cliente para criar o usuário associado
        user, message = create_user(db, user_data, is_admin=False, client_id=client.id)
        
        if not user:
            # Se houve erro na criação do usuário, fazer rollback
            db.rollback()
            logger.error(f"Erro ao criar usuário para o cliente: {message}")
            return None, f"Erro ao criar usuário: {message}"
        
        # Se tudo correu bem, confirmar a transação
        db.commit()
        logger.info(f"Cliente e usuário criados com sucesso: {client.id}")
        return client, "Cliente e usuário criados com sucesso"
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao criar cliente com usuário: {str(e)}")
        return None, f"Erro ao criar cliente com usuário: {str(e)}"
    
    except Exception as e:
        db.rollback()
        logger.error(f"Erro inesperado ao criar cliente com usuário: {str(e)}")
        return None, f"Erro inesperado: {str(e)}" 