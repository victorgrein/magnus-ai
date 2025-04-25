from sqlalchemy import Column, String, UUID, DateTime, ForeignKey, JSON, Text, BigInteger, CheckConstraint
from sqlalchemy.sql import func
from src.config.database import Base
import uuid

class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"))
    ext_id = Column(String)
    name = Column(String)
    meta = Column(JSON, default={})

class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    model = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    instruction = Column(Text)
    config = Column(JSON, default={})

    __table_args__ = (
        CheckConstraint("type IN ('llm', 'sequential', 'parallel', 'loop')", name='check_agent_type'),
    )

class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(UUID(as_uuid=True))
    sender = Column(String)
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 