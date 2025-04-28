from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from src.models.models import Agent
from src.schemas.schemas import AgentCreate
from typing import List, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

def get_agent(db: Session, agent_id: uuid.UUID) -> Optional[Agent]:
    """Busca um agente pelo ID"""
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            logger.warning(f"Agente não encontrado: {agent_id}")
            return None
        return agent
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar agente {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar agente"
        )

def get_agents_by_client(
    db: Session, 
    client_id: uuid.UUID, 
    skip: int = 0, 
    limit: int = 100,
    active_only: bool = True
) -> List[Agent]:
    """Busca agentes de um cliente com paginação"""
    try:
        query = db.query(Agent).filter(Agent.client_id == client_id)
        
        if active_only:
            query = query.filter(Agent.is_active == True)
            
        return query.offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar agentes do cliente {client_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar agentes"
        )

def create_agent(db: Session, agent: AgentCreate) -> Agent:
    """Cria um novo agente"""
    try:
        db_agent = Agent(**agent.model_dump())
        db.add(db_agent)
        db.commit()
        db.refresh(db_agent)
        logger.info(f"Agente criado com sucesso: {db_agent.id}")
        return db_agent
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao criar agente: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar agente"
        )

def update_agent(db: Session, agent_id: uuid.UUID, agent: AgentCreate) -> Optional[Agent]:
    """Atualiza um agente existente"""
    try:
        db_agent = get_agent(db, agent_id)
        if not db_agent:
            return None
            
        for key, value in agent.model_dump().items():
            setattr(db_agent, key, value)
            
        db.commit()
        db.refresh(db_agent)
        logger.info(f"Agente atualizado com sucesso: {agent_id}")
        return db_agent
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao atualizar agente {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar agente"
        )

def delete_agent(db: Session, agent_id: uuid.UUID) -> bool:
    """Remove um agente (soft delete)"""
    try:
        db_agent = get_agent(db, agent_id)
        if not db_agent:
            return False
            
        db_agent.is_active = False
        db.commit()
        logger.info(f"Agente desativado com sucesso: {agent_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao desativar agente {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao desativar agente"
        )

def activate_agent(db: Session, agent_id: uuid.UUID) -> bool:
    """Reativa um agente"""
    try:
        db_agent = get_agent(db, agent_id)
        if not db_agent:
            return False
            
        db_agent.is_active = True
        db.commit()
        logger.info(f"Agente reativado com sucesso: {agent_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao reativar agente {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao reativar agente"
        ) 