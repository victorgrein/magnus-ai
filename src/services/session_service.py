from google.adk.sessions import DatabaseSessionService
from sqlalchemy.orm import Session
from src.models.models import Session as SessionModel
from google.adk.events import Event
from google.adk.sessions import Session as SessionADK
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from src.services.agent_service import get_agent, get_agents_by_client
from src.services.contact_service import get_contact

import uuid
import logging

logger = logging.getLogger(__name__)


def get_sessions_by_client(
    db: Session,
    client_id: uuid.UUID,
) -> List[SessionModel]:
    """Busca sessões de um cliente com paginação"""
    try:
        agents_by_client = get_agents_by_client(db, client_id)
        sessions = []
        for agent in agents_by_client:
            sessions.extend(get_sessions_by_agent(db, agent.id))

        return sessions
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar sessões do cliente {client_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar sessões",
        )


def get_sessions_by_agent(
    db: Session,
    agent_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> List[SessionModel]:
    """Busca sessões de um agente com paginação"""
    try:
        agent_id_str = str(agent_id)
        query = db.query(SessionModel).filter(SessionModel.app_name == agent_id_str)

        return query.offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Erro ao buscar sessões do agente {agent_id_str}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar sessões",
        )


def get_session_by_id(
    session_service: DatabaseSessionService, session_id: str
) -> Optional[SessionADK]:
    """Busca uma sessão pelo ID"""
    try:
        if not session_id or "_" not in session_id:
            logger.error(f"ID de sessão inválido: {session_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID de sessão inválido. Formato esperado: app_name_user_id",
            )
            
        parts = session_id.split("_", 1)
        if len(parts) != 2:
            logger.error(f"Formato de ID de sessão inválido: {session_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de ID de sessão inválido. Formato esperado: app_name_user_id",
            )
            
        user_id, app_name = parts
        
        session = session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        
        if session is None:
            logger.error(f"Sessão não encontrada: {session_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sessão não encontrada: {session_id}",
            )
            
        return session
    except Exception as e:
        logger.error(f"Erro ao buscar sessão {session_id}: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar sessão: {str(e)}",
        )


def delete_session(session_service: DatabaseSessionService, session_id: str) -> None:
    """Deleta uma sessão pelo ID"""
    try:
        session = get_session_by_id(session_service, session_id)
        # Se chegou aqui, a sessão existe (get_session_by_id já valida)
        
        session_service.delete_session(
            app_name=session.app_name,
            user_id=session.user_id,
            session_id=session_id,
        )
        return None
    except HTTPException:
        # Repassa exceções HTTP do get_session_by_id
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar sessão {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar sessão: {str(e)}",
        )


def get_session_events(
    session_service: DatabaseSessionService, session_id: str
) -> List[Event]:
    """Busca os eventos de uma sessão pelo ID"""
    try:
        session = get_session_by_id(session_service, session_id)
        # Se chegou aqui, a sessão existe (get_session_by_id já valida)
        
        if not hasattr(session, 'events') or session.events is None:
            return []
            
        return session.events
    except HTTPException:
        # Repassa exceções HTTP do get_session_by_id
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar eventos da sessão {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar eventos da sessão: {str(e)}",
        )
