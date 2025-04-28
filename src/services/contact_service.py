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
    """Search for a contact by ID"""
    try:
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            logger.warning(f"Contact not found: {contact_id}")
            return None
        return contact
    except SQLAlchemyError as e:
        logger.error(f"Error searching for contact {contact_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error searching for contact"
        )

def get_contacts_by_client(db: Session, client_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Contact]:
    """Search for contacts of a client with pagination"""
    try:
        return db.query(Contact).filter(Contact.client_id == client_id).offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Error searching for contacts of client {client_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error searching for contacts"
        )

def create_contact(db: Session, contact: ContactCreate) -> Contact:
    """Create a new contact"""
    try:
        db_contact = Contact(**contact.model_dump())
        db.add(db_contact)
        db.commit()
        db.refresh(db_contact)
        logger.info(f"Contact created successfully: {db_contact.id}")
        return db_contact
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error creating contact: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating contact"
        )

def update_contact(db: Session, contact_id: uuid.UUID, contact: ContactCreate) -> Optional[Contact]:
    """Update an existing contact"""
    try:
        db_contact = get_contact(db, contact_id)
        if not db_contact:
            return None
            
        for key, value in contact.model_dump().items():
            setattr(db_contact, key, value)
            
        db.commit()
        db.refresh(db_contact)
        logger.info(f"Contact updated successfully: {contact_id}")
        return db_contact
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error updating contact {contact_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating contact"
        )

def delete_contact(db: Session, contact_id: uuid.UUID) -> bool:
    """Remove a contact"""
    try:
        db_contact = get_contact(db, contact_id)
        if not db_contact:
            return False
            
        db.delete(db_contact)
        db.commit()
        logger.info(f"Contact removed successfully: {contact_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error removing contact {contact_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error removing contact"
        ) 