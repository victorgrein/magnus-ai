from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

from src.config.database import get_db
from src.core.jwt_middleware import get_jwt_token, verify_admin
from src.schemas.audit import AuditLogResponse, AuditLogFilter
from src.services.audit_service import get_audit_logs, create_audit_log
from src.services.user_service import get_admin_users, create_admin_user, deactivate_user
from src.schemas.user import UserResponse, AdminUserCreate

router = APIRouter(
    prefix="/admin",
    tags=["administração"],
    dependencies=[Depends(verify_admin)],  # Todas as rotas requerem permissão de admin
    responses={403: {"description": "Permissão negada"}},
)

# Rotas para auditoria
@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def read_audit_logs(
    filters: AuditLogFilter = Depends(),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    """
    Obter logs de auditoria com filtros opcionais
    
    Args:
        filters: Filtros para busca de logs
        db: Sessão do banco de dados
        payload: Payload do token JWT
        
    Returns:
        List[AuditLogResponse]: Lista de logs de auditoria
    """
    return get_audit_logs(
        db,
        skip=filters.skip,
        limit=filters.limit,
        user_id=filters.user_id,
        action=filters.action,
        resource_type=filters.resource_type,
        resource_id=filters.resource_id,
        start_date=filters.start_date,
        end_date=filters.end_date
    )

# Rotas para administradores
@router.get("/users", response_model=List[UserResponse])
async def read_admin_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    """
    Listar usuários administradores
    
    Args:
        skip: Número de registros para pular
        limit: Número máximo de registros para retornar
        db: Sessão do banco de dados
        payload: Payload do token JWT
        
    Returns:
        List[UserResponse]: Lista de usuários administradores
    """
    return get_admin_users(db, skip, limit)

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_admin_user(
    user_data: AdminUserCreate,
    request: Request,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    """
    Criar um novo usuário administrador
    
    Args:
        user_data: Dados do usuário a ser criado
        request: Objeto Request do FastAPI
        db: Sessão do banco de dados
        payload: Payload do token JWT
        
    Returns:
        UserResponse: Dados do usuário criado
        
    Raises:
        HTTPException: Se houver erro na criação
    """
    # Obter o ID do usuário atual
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível identificar o usuário logado"
        )
    
    # Criar o usuário administrador
    user, message = create_admin_user(db, user_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Registrar ação no log de auditoria
    create_audit_log(
        db,
        user_id=uuid.UUID(user_id),
        action="create",
        resource_type="admin_user",
        resource_id=str(user.id),
        details={"email": user.email},
        request=request
    )
    
    return user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_admin_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    """
    Desativar um usuário administrador (não exclui, apenas desativa)
    
    Args:
        user_id: ID do usuário a ser desativado
        request: Objeto Request do FastAPI
        db: Sessão do banco de dados
        payload: Payload do token JWT
        
    Raises:
        HTTPException: Se houver erro na desativação
    """
    # Obter o ID do usuário atual
    current_user_id = payload.get("user_id")
    if not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível identificar o usuário logado"
        )
    
    # Não permitir desativar a si mesmo
    if str(user_id) == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível desativar seu próprio usuário"
        )
    
    # Desativar o usuário
    success, message = deactivate_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Registrar ação no log de auditoria
    create_audit_log(
        db,
        user_id=uuid.UUID(current_user_id),
        action="deactivate",
        resource_type="admin_user",
        resource_id=str(user_id),
        details=None,
        request=request
    ) 