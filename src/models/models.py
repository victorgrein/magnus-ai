import os
from sqlalchemy import (
    Column,
    String,
    UUID,
    DateTime,
    ForeignKey,
    JSON,
    Text,
    CheckConstraint,
    Boolean,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref
from src.config.database import Base
import uuid


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    client_id = Column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=True
    )
    is_active = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    verification_token_expiry = Column(DateTime(timezone=True), nullable=True)
    password_reset_token = Column(String, nullable=True)
    password_reset_expiry = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship with Client (One-to-One, optional for administrators)
    client = relationship(
        "Client", backref=backref("user", uselist=False, cascade="all, delete-orphan")
    )


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
    agent_card_url = Column(String, nullable=True)
    config = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "type IN ('llm', 'sequential', 'parallel', 'loop', 'a2a')",
            name="check_agent_type",
        ),
    )

    @property
    def agent_card_url_property(self) -> str:
        """Virtual URL for the agent card"""
        if self.agent_card_url:
            return self.agent_card_url

        return f"{os.getenv('API_URL', '')}/api/v1/a2a/{self.id}/.well-known/agent.json"

    def to_dict(self):
        """Converts the object to a dictionary, converting UUIDs to strings"""
        result = {}
        for key, value in self.__dict__.items():
            if key.startswith("_"):
                continue
            if isinstance(value, uuid.UUID):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = self._convert_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    (
                        self._convert_dict(item)
                        if isinstance(item, dict)
                        else str(item) if isinstance(item, uuid.UUID) else item
                    )
                    for item in value
                ]
            else:
                result[key] = value
        result["agent_card_url"] = self.agent_card_url_property
        return result

    def _convert_dict(self, d):
        """Converts UUIDs to a dictionary for strings"""
        result = {}
        for key, value in d.items():
            if isinstance(value, uuid.UUID):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = self._convert_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    (
                        self._convert_dict(item)
                        if isinstance(item, dict)
                        else str(item) if isinstance(item, uuid.UUID) else item
                    )
                    for item in value
                ]
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
    tools = Column(JSON, nullable=False, default=[])
    type = Column(String, nullable=False, default="official")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "type IN ('official', 'community')", name="check_mcp_server_type"
        ),
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


class Session(Base):
    __tablename__ = "sessions"
    # The directive below makes Alembic ignore this table in migrations
    __table_args__ = {"extend_existing": True, "info": {"skip_autogenerate": True}}

    id = Column(String, primary_key=True)
    app_name = Column(String)
    user_id = Column(String)
    state = Column(JSON)
    create_time = Column(DateTime(timezone=True))
    update_time = Column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship with User
    user = relationship("User", backref="audit_logs")
