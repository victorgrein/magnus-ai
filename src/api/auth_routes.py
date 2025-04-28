from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models.models import User
from src.schemas.user import (
    UserCreate,
    UserResponse,
    UserLogin,
    TokenResponse,
    ForgotPassword,
    PasswordReset,
    MessageResponse,
)
from src.services.user_service import (
    create_user,
    verify_email,
    resend_verification,
    forgot_password,
    reset_password,
)
from src.services.auth_service import (
    authenticate_user,
    create_access_token,
    get_current_admin_user,
    get_current_user,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["autenticação"],
    responses={404: {"description": "Não encontrado"}},
)


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Registra um novo usuário (cliente) no sistema

    Args:
        user_data: Dados do usuário a ser registrado
        db: Sessão do banco de dados

    Returns:
        UserResponse: Dados do usuário criado

    Raises:
        HTTPException: Se houver erro no registro
    """
    user, message = create_user(db, user_data, is_admin=False)
    if not user:
        logger.error(f"Erro ao registrar usuário: {message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    logger.info(f"Usuário registrado com sucesso: {user.email}")
    return user


@router.post(
    "/register-admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_admin(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    """
    Registra um novo administrador no sistema.
    Apenas administradores existentes podem criar novos administradores.

    Args:
        user_data: Dados do administrador a ser registrado
        db: Sessão do banco de dados
        current_admin: Administrador atual (autenticado)

    Returns:
        UserResponse: Dados do administrador criado

    Raises:
        HTTPException: Se houver erro no registro
    """
    user, message = create_user(db, user_data, is_admin=True)
    if not user:
        logger.error(f"Erro ao registrar administrador: {message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    logger.info(
        f"Administrador registrado com sucesso: {user.email} (criado por {current_admin.email})"
    )
    return user


@router.get("/verify-email/{token}", response_model=MessageResponse)
async def verify_user_email(token: str, db: Session = Depends(get_db)):
    """
    Verifica o email de um usuário usando o token fornecido

    Args:
        token: Token de verificação
        db: Sessão do banco de dados

    Returns:
        MessageResponse: Mensagem de sucesso

    Raises:
        HTTPException: Se o token for inválido ou expirado
    """
    success, message = verify_email(db, token)
    if not success:
        logger.warning(f"Falha na verificação de email: {message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    logger.info(f"Email verificado com sucesso usando token: {token}")
    return {"message": message}


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification_email(
    email_data: ForgotPassword, db: Session = Depends(get_db)
):
    """
    Reenvia o email de verificação para o usuário

    Args:
        email_data: Email do usuário
        db: Sessão do banco de dados

    Returns:
        MessageResponse: Mensagem de sucesso

    Raises:
        HTTPException: Se houver erro no reenvio
    """
    success, message = resend_verification(db, email_data.email)
    if not success:
        logger.warning(f"Falha no reenvio de verificação: {message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    logger.info(f"Email de verificação reenviado com sucesso para: {email_data.email}")
    return {"message": message}


@router.post("/login", response_model=TokenResponse)
async def login_for_access_token(form_data: UserLogin, db: Session = Depends(get_db)):
    """
    Realiza login e retorna um token de acesso JWT

    Args:
        form_data: Dados de login (email e senha)
        db: Sessão do banco de dados

    Returns:
        TokenResponse: Token de acesso e tipo

    Raises:
        HTTPException: Se as credenciais forem inválidas
    """
    user = authenticate_user(db, form_data.email, form_data.password)
    if not user:
        logger.warning(
            f"Tentativa de login com credenciais inválidas: {form_data.email}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user)
    logger.info(f"Login realizado com sucesso para usuário: {user.email}")
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_user_password(
    email_data: ForgotPassword, db: Session = Depends(get_db)
):
    """
    Inicia o processo de recuperação de senha

    Args:
        email_data: Email do usuário
        db: Sessão do banco de dados

    Returns:
        MessageResponse: Mensagem de sucesso

    Raises:
        HTTPException: Se houver erro no processo
    """
    success, message = forgot_password(db, email_data.email)
    # Sempre retornamos a mesma mensagem por segurança
    return {
        "message": "Se o email estiver cadastrado, você receberá instruções para redefinir sua senha."
    }


@router.post("/reset-password", response_model=MessageResponse)
async def reset_user_password(reset_data: PasswordReset, db: Session = Depends(get_db)):
    """
    Redefine a senha do usuário usando o token fornecido

    Args:
        reset_data: Token e nova senha
        db: Sessão do banco de dados

    Returns:
        MessageResponse: Mensagem de sucesso

    Raises:
        HTTPException: Se o token for inválido ou expirado
    """
    success, message = reset_password(db, reset_data.token, reset_data.new_password)
    if not success:
        logger.warning(f"Falha na redefinição de senha: {message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    logger.info("Senha redefinida com sucesso")
    return {"message": message}


@router.post("/me", response_model=UserResponse)
async def get_current_user(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Obtém os dados do usuário autenticado

    Args:
        db: Sessão do banco de dados
        current_user: Usuário autenticado

    Returns:
        UserResponse: Dados do usuário autenticado

    Raises:
        HTTPException: Se o usuário não estiver autenticado
    """
    return current_user
