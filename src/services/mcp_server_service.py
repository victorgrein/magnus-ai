from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from src.models.models import MCPServer
from src.schemas.schemas import MCPServerCreate
from typing import List, Optional
import uuid
import logging

logger = logging.getLogger(__name__)


def get_mcp_server(db: Session, server_id: uuid.UUID) -> Optional[MCPServer]:
    """Search for an MCP server by ID"""
    try:
        server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
        if not server:
            logger.warning(f"MCP server not found: {server_id}")
            return None
        return server
    except SQLAlchemyError as e:
        logger.error(f"Error searching for MCP server {server_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error searching for MCP server",
        )


def get_mcp_servers(db: Session, skip: int = 0, limit: int = 100) -> List[MCPServer]:
    """Search for all MCP servers with pagination"""
    try:
        return db.query(MCPServer).offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Error searching for MCP servers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error searching for MCP servers",
        )


def create_mcp_server(db: Session, server: MCPServerCreate) -> MCPServer:
    """Create a new MCP server"""
    try:
        db_server = MCPServer(**server.model_dump())
        db.add(db_server)
        db.commit()
        db.refresh(db_server)
        logger.info(f"MCP server created successfully: {db_server.id}")
        return db_server
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error creating MCP server: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating MCP server",
        )


def update_mcp_server(
    db: Session, server_id: uuid.UUID, server: MCPServerCreate
) -> Optional[MCPServer]:
    """Update an existing MCP server"""
    try:
        db_server = get_mcp_server(db, server_id)
        if not db_server:
            return None

        for key, value in server.model_dump().items():
            setattr(db_server, key, value)

        db.commit()
        db.refresh(db_server)
        logger.info(f"MCP server updated successfully: {server_id}")
        return db_server
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error updating MCP server {server_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating MCP server",
        )


def delete_mcp_server(db: Session, server_id: uuid.UUID) -> bool:
    """Remove an MCP server"""
    try:
        db_server = get_mcp_server(db, server_id)
        if not db_server:
            return False

        db.delete(db_server)
        db.commit()
        logger.info(f"MCP server removed successfully: {server_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error removing MCP server {server_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error removing MCP server",
        )
