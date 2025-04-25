from sqlalchemy.orm import Session
from src.models.models import Contact
from src.schemas.schemas import ContactCreate
from typing import List
import uuid

def get_contact(db: Session, contact_id: uuid.UUID) -> Contact:
    return db.query(Contact).filter(Contact.id == contact_id).first()

def get_contacts_by_client(db: Session, client_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Contact]:
    return db.query(Contact).filter(Contact.client_id == client_id).offset(skip).limit(limit).all()

def create_contact(db: Session, contact: ContactCreate) -> Contact:
    db_contact = Contact(**contact.model_dump())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

def update_contact(db: Session, contact_id: uuid.UUID, contact: ContactCreate) -> Contact:
    db_contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if db_contact:
        for key, value in contact.model_dump().items():
            setattr(db_contact, key, value)
        db.commit()
        db.refresh(db_contact)
    return db_contact

def delete_contact(db: Session, contact_id: uuid.UUID) -> bool:
    db_contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if db_contact:
        db.delete(db_contact)
        db.commit()
        return True
    return False 