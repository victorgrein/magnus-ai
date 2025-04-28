from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from src.models.models import Contact
from src.schemas.schemas import ContactCreate
from typing import List, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

def get_contact(db: Session, contact_id: uuid.UUID) -> Optional[Contact]:
    """Busca um contato pelo ID"""
    try:
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            logger.warning(f"Contato não encontrado: {contact_id}")
            return None
        return contact
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar contato {contact_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar contato"
        )

def get_contacts_by_client(db: Session, client_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Contact]:
    """Busca contatos de um cliente com paginação"""
    try:
        return db.query(Contact).filter(Contact.client_id == client_id).offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar contatos do cliente {client_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar contatos"
        )

def create_contact(db: Session, contact: ContactCreate) -> Contact:
    """Cria um novo contato"""
    try:
        db_contact = Contact(**contact.model_dump())
        db.add(db_contact)
        db.commit()
        db.refresh(db_contact)
        logger.info(f"Contato criado com sucesso: {db_contact.id}")
        return db_contact
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao criar contato: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar contato"
        )

def update_contact(db: Session, contact_id: uuid.UUID, contact: ContactCreate) -> Optional[Contact]:
    """Atualiza um contato existente"""
    try:
        db_contact = get_contact(db, contact_id)
        if not db_contact:
            return None
            
        for key, value in contact.model_dump().items():
            setattr(db_contact, key, value)
            
        db.commit()
        db.refresh(db_contact)
        logger.info(f"Contato atualizado com sucesso: {contact_id}")
        return db_contact
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao atualizar contato {contact_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar contato"
        )

def delete_contact(db: Session, contact_id: uuid.UUID) -> bool:
    """Remove um contato"""
    try:
        db_contact = get_contact(db, contact_id)
        if not db_contact:
            return False
            
        db.delete(db_contact)
        db.commit()
        logger.info(f"Contato removido com sucesso: {contact_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao remover contato {contact_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover contato"
        ) 