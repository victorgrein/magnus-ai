from sqlalchemy.orm import Session
from src.models.models import Message
from src.schemas.schemas import MessageCreate
from typing import List
import uuid

def get_message(db: Session, message_id: int) -> Message:
    return db.query(Message).filter(Message.id == message_id).first()

def get_messages_by_session(db: Session, session_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Message]:
    return db.query(Message).filter(Message.session_id == session_id).offset(skip).limit(limit).all()

def create_message(db: Session, message: MessageCreate) -> Message:
    db_message = Message(**message.model_dump())
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

def update_message(db: Session, message_id: int, message: MessageCreate) -> Message:
    db_message = db.query(Message).filter(Message.id == message_id).first()
    if db_message:
        for key, value in message.model_dump().items():
            setattr(db_message, key, value)
        db.commit()
        db.refresh(db_message)
    return db_message

def delete_message(db: Session, message_id: int) -> bool:
    db_message = db.query(Message).filter(Message.id == message_id).first()
    if db_message:
        db.delete(db_message)
        db.commit()
        return True
    return False 