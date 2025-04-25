from sqlalchemy.orm import Session
from src.models.models import Client
from src.schemas.schemas import ClientCreate
from typing import List
import uuid

def get_client(db: Session, client_id: uuid.UUID) -> Client:
    return db.query(Client).filter(Client.id == client_id).first()

def get_clients(db: Session, skip: int = 0, limit: int = 100) -> List[Client]:
    return db.query(Client).offset(skip).limit(limit).all()

def create_client(db: Session, client: ClientCreate) -> Client:
    db_client = Client(**client.model_dump())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

def update_client(db: Session, client_id: uuid.UUID, client: ClientCreate) -> Client:
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if db_client:
        for key, value in client.model_dump().items():
            setattr(db_client, key, value)
        db.commit()
        db.refresh(db_client)
    return db_client

def delete_client(db: Session, client_id: uuid.UUID) -> bool:
    db_client = db.query(Client).filter(Client.id == client_id).first()
    if db_client:
        db.delete(db_client)
        db.commit()
        return True
    return False 