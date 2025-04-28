from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.models.models import AuditLog, User
from datetime import datetime
from fastapi import Request
from typing import Optional, Dict, Any, List
import uuid
import logging
import json

logger = logging.getLogger(__name__)

def create_audit_log(
    db: Session,
    user_id: Optional[uuid.UUID],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
) -> Optional[AuditLog]:
    """
    Cria um novo registro de auditoria
    
    Args:
        db: Sessão do banco de dados
        user_id: ID do usuário que realizou a ação (ou None se anônimo)
        action: Ação realizada (ex: "create", "update", "delete")
        resource_type: Tipo de recurso (ex: "client", "agent", "user")
        resource_id: ID do recurso (opcional)
        details: Detalhes adicionais da ação (opcional)
        request: Objeto Request do FastAPI (opcional, para obter IP e User-Agent)
        
    Returns:
        Optional[AuditLog]: Registro de auditoria criado ou None em caso de erro
    """
    try:
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = request.client.host if hasattr(request, 'client') else None
            user_agent = request.headers.get("user-agent")
        
        # Converter details para formato serializável
        if details:
            # Converter UUIDs para strings
            for key, value in details.items():
                if isinstance(value, uuid.UUID):
                    details[key] = str(value)
        
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        
        logger.info(
            f"Audit log criado: {action} em {resource_type}" +
            (f" (ID: {resource_id})" if resource_id else "")
        )
        
        return audit_log
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao criar registro de auditoria: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao criar registro de auditoria: {str(e)}")
        return None

def get_audit_logs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[uuid.UUID] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[AuditLog]:
    """
    Obtém registros de auditoria com filtros opcionais
    
    Args:
        db: Sessão do banco de dados
        skip: Número de registros para pular
        limit: Número máximo de registros para retornar
        user_id: Filtrar por ID do usuário
        action: Filtrar por ação
        resource_type: Filtrar por tipo de recurso
        resource_id: Filtrar por ID do recurso
        start_date: Data inicial
        end_date: Data final
        
    Returns:
        List[AuditLog]: Lista de registros de auditoria
    """
    query = db.query(AuditLog)
    
    # Aplicar filtros, se fornecidos
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    
    if action:
        query = query.filter(AuditLog.action == action)
    
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    
    if resource_id:
        query = query.filter(AuditLog.resource_id == resource_id)
    
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)
    
    # Ordenar por data de criação (mais recentes primeiro)
    query = query.order_by(AuditLog.created_at.desc())
    
    # Aplicar paginação
    query = query.offset(skip).limit(limit)
    
    return query.all() 