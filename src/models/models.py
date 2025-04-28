from sqlalchemy import Column, String, UUID, DateTime, ForeignKey, JSON, Text, BigInteger, CheckConstraint, Boolean
from sqlalchemy.sql import func
from src.config.database import Base
import uuid

class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"))
    ext_id = Column(String)
    name = Column(String)
    meta = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String, nullable=False)
    model = Column(String, nullable=True, default="")
    api_key = Column(String, nullable=True, default="")
    instruction = Column(Text)
    config = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("type IN ('llm', 'sequential', 'parallel', 'loop')", name='check_agent_type'),
    )

    def to_dict(self):
        """Converte o objeto para dicionário, convertendo UUIDs para strings"""
        result = {}
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                continue
            if isinstance(value, uuid.UUID):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = self._convert_dict(value)
            elif isinstance(value, list):
                result[key] = [self._convert_dict(item) if isinstance(item, dict) else str(item) if isinstance(item, uuid.UUID) else item for item in value]
            else:
                result[key] = value
        return result

    def _convert_dict(self, d):
        """Converte UUIDs em um dicionário para strings"""
        result = {}
        for key, value in d.items():
            if isinstance(value, uuid.UUID):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = self._convert_dict(value)
            elif isinstance(value, list):
                result[key] = [self._convert_dict(item) if isinstance(item, dict) else str(item) if isinstance(item, uuid.UUID) else item for item in value]
            else:
                result[key] = value
        return result

class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    config_json = Column(JSON, nullable=False, default={})
    environments = Column(JSON, nullable=False, default={})
    type = Column(String, nullable=False, default="official")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        CheckConstraint("type IN ('official', 'community')", name='check_mcp_server_type'),
    )

class Tool(Base):
    __tablename__ = "tools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    config_json = Column(JSON, nullable=False, default={})
    environments = Column(JSON, nullable=False, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())