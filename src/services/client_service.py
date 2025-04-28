from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from src.models.models import Client
from src.schemas.schemas import ClientCreate
from typing import List, Optional
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