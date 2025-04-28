from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from src.models.models import Tool
from src.schemas.schemas import ToolCreate
from typing import List, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

def get_tool(db: Session, tool_id: uuid.UUID) -> Optional[Tool]:
    """Busca uma ferramenta pelo ID"""
    try:
        tool = db.query(Tool).filter(Tool.id == tool_id).first()
        if not tool:
            logger.warning(f"Ferramenta não encontrada: {tool_id}")
            return None
        return tool
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar ferramenta {tool_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar ferramenta"
        )

def get_tools(db: Session, skip: int = 0, limit: int = 100) -> List[Tool]:
    """Busca todas as ferramentas com paginação"""
    try:
        return db.query(Tool).offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar ferramentas: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar ferramentas"
        )

def create_tool(db: Session, tool: ToolCreate) -> Tool:
    """Cria uma nova ferramenta"""
    try:
        db_tool = Tool(**tool.model_dump())
        db.add(db_tool)
        db.commit()
        db.refresh(db_tool)
        logger.info(f"Ferramenta criada com sucesso: {db_tool.id}")
        return db_tool
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao criar ferramenta: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar ferramenta"
        )

def update_tool(db: Session, tool_id: uuid.UUID, tool: ToolCreate) -> Optional[Tool]:
    """Atualiza uma ferramenta existente"""
    try:
        db_tool = get_tool(db, tool_id)
        if not db_tool:
            return None
            
        for key, value in tool.model_dump().items():
            setattr(db_tool, key, value)
            
        db.commit()
        db.refresh(db_tool)
        logger.info(f"Ferramenta atualizada com sucesso: {tool_id}")
        return db_tool
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao atualizar ferramenta {tool_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar ferramenta"
        )

def delete_tool(db: Session, tool_id: uuid.UUID) -> bool:
    """Remove uma ferramenta"""
    try:
        db_tool = get_tool(db, tool_id)
        if not db_tool:
            return False
            
        db.delete(db_tool)
        db.commit()
        logger.info(f"Ferramenta removida com sucesso: {tool_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao remover ferramenta {tool_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover ferramenta"
        ) 