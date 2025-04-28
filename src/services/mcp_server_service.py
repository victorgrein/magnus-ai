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
    """Busca um servidor MCP pelo ID"""
    try:
        server = db.query(MCPServer).filter(MCPServer.id == server_id).first()
        if not server:
            logger.warning(f"Servidor MCP não encontrado: {server_id}")
            return None
        return server
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar servidor MCP {server_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar servidor MCP"
        )

def get_mcp_servers(db: Session, skip: int = 0, limit: int = 100) -> List[MCPServer]:
    """Busca todos os servidores MCP com paginação"""
    try:
        return db.query(MCPServer).offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar servidores MCP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar servidores MCP"
        )

def create_mcp_server(db: Session, server: MCPServerCreate) -> MCPServer:
    """Cria um novo servidor MCP"""
    try:
        db_server = MCPServer(**server.model_dump())
        db.add(db_server)
        db.commit()
        db.refresh(db_server)
        logger.info(f"Servidor MCP criado com sucesso: {db_server.id}")
        return db_server
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao criar servidor MCP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar servidor MCP"
        )

def update_mcp_server(db: Session, server_id: uuid.UUID, server: MCPServerCreate) -> Optional[MCPServer]:
    """Atualiza um servidor MCP existente"""
    try:
        db_server = get_mcp_server(db, server_id)
        if not db_server:
            return None
            
        for key, value in server.model_dump().items():
            setattr(db_server, key, value)
            
        db.commit()
        db.refresh(db_server)
        logger.info(f"Servidor MCP atualizado com sucesso: {server_id}")
        return db_server
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao atualizar servidor MCP {server_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar servidor MCP"
        )

def delete_mcp_server(db: Session, server_id: uuid.UUID) -> bool:
    """Remove um servidor MCP"""
    try:
        db_server = get_mcp_server(db, server_id)
        if not db_server:
            return False
            
        db.delete(db_server)
        db.commit()
        logger.info(f"Servidor MCP removido com sucesso: {server_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao remover servidor MCP {server_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover servidor MCP"
        ) 