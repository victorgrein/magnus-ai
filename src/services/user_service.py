from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.models.models import User, Client
from src.schemas.user import UserCreate, UserResponse
from src.utils.security import get_password_hash, verify_password, generate_token
from src.services.email_service import send_verification_email, send_password_reset_email
from datetime import datetime, timedelta
import uuid
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

def create_user(db: Session, user_data: UserCreate, is_admin: bool = False, client_id: Optional[uuid.UUID] = None) -> Tuple[Optional[User], str]:
    """
    Cria um novo usuário no sistema
    
    Args:
        db: Sessão do banco de dados
        user_data: Dados do usuário a ser criado
        is_admin: Se o usuário é um administrador
        client_id: ID do cliente associado (opcional, será criado um novo se não fornecido)
        
    Returns:
        Tuple[Optional[User], str]: Tupla com o usuário criado (ou None em caso de erro) e mensagem de status
    """
    try:
        # Verificar se email já existe
        db_user = db.query(User).filter(User.email == user_data.email).first()
        if db_user:
            logger.warning(f"Tentativa de cadastro com email já existente: {user_data.email}")
            return None, "Email já cadastrado"
        
        # Criar token de verificação
        verification_token = generate_token()
        token_expiry = datetime.utcnow() + timedelta(hours=24)
        
        # Iniciar transação
        user = None
        local_client_id = client_id
        
        try:
            # Se não for admin e não tiver client_id, criar um cliente associado
            if not is_admin and local_client_id is None:
                client = Client(name=user_data.name)
                db.add(client)
                db.flush()  # Obter o ID do cliente
                local_client_id = client.id
            
            # Criar usuário
            user = User(
                email=user_data.email,
                password_hash=get_password_hash(user_data.password),
                client_id=local_client_id,
                is_admin=is_admin,
                is_active=False,  # Inativo até verificar email
                email_verified=False,
                verification_token=verification_token,
                verification_token_expiry=token_expiry
            )
            db.add(user)
            db.commit()
            
            # Enviar email de verificação
            email_sent = send_verification_email(user.email, verification_token)
            if not email_sent:
                logger.error(f"Falha ao enviar email de verificação para {user.email}")
                # Não fazemos rollback aqui, apenas logamos o erro
            
            logger.info(f"Usuário criado com sucesso: {user.email}")
            return user, "Usuário criado com sucesso. Verifique seu email para ativar sua conta."
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Erro ao criar usuário: {str(e)}")
            return None, f"Erro ao criar usuário: {str(e)}"
            
    except Exception as e:
        logger.error(f"Erro inesperado ao criar usuário: {str(e)}")
        return None, f"Erro inesperado: {str(e)}"

def verify_email(db: Session, token: str) -> Tuple[bool, str]:
    """
    Verifica o email do usuário usando o token fornecido
    
    Args:
        db: Sessão do banco de dados
        token: Token de verificação
        
    Returns:
        Tuple[bool, str]: Tupla com status da verificação e mensagem
    """
    try:
        # Buscar usuário pelo token
        user = db.query(User).filter(User.verification_token == token).first()
        
        if not user:
            logger.warning(f"Tentativa de verificação com token inválido: {token}")
            return False, "Token de verificação inválido"
        
        # Verificar se o token expirou
        now = datetime.utcnow()
        expiry = user.verification_token_expiry
        
        # Garantir que ambas as datas sejam do mesmo tipo (aware ou naive)
        if expiry.tzinfo is not None and now.tzinfo is None:
            # Se expiry tem fuso e now não, converter now para ter fuso
            now = now.replace(tzinfo=expiry.tzinfo)
        elif now.tzinfo is not None and expiry.tzinfo is None:
            # Se now tem fuso e expiry não, converter expiry para ter fuso
            expiry = expiry.replace(tzinfo=now.tzinfo)
            
        if expiry < now:
            logger.warning(f"Tentativa de verificação com token expirado para usuário: {user.email}")
            return False, "Token de verificação expirado"
        
        # Atualizar usuário
        user.email_verified = True
        user.is_active = True
        user.verification_token = None
        user.verification_token_expiry = None
        
        db.commit()
        logger.info(f"Email verificado com sucesso para usuário: {user.email}")
        return True, "Email verificado com sucesso. Sua conta está ativa."
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao verificar email: {str(e)}")
        return False, f"Erro ao verificar email: {str(e)}"
    
    except Exception as e:
        logger.error(f"Erro inesperado ao verificar email: {str(e)}")
        return False, f"Erro inesperado: {str(e)}"

def resend_verification(db: Session, email: str) -> Tuple[bool, str]:
    """
    Reenvia o email de verificação
    
    Args:
        db: Sessão do banco de dados
        email: Email do usuário
        
    Returns:
        Tuple[bool, str]: Tupla com status da operação e mensagem
    """
    try:
        # Buscar usuário pelo email
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            logger.warning(f"Tentativa de reenvio de verificação para email inexistente: {email}")
            return False, "Email não encontrado"
        
        if user.email_verified:
            logger.info(f"Tentativa de reenvio de verificação para email já verificado: {email}")
            return False, "Email já foi verificado"
        
        # Gerar novo token
        verification_token = generate_token()
        token_expiry = datetime.utcnow() + timedelta(hours=24)
        
        # Atualizar usuário
        user.verification_token = verification_token
        user.verification_token_expiry = token_expiry
        
        db.commit()
        
        # Enviar email
        email_sent = send_verification_email(user.email, verification_token)
        if not email_sent:
            logger.error(f"Falha ao reenviar email de verificação para {user.email}")
            return False, "Falha ao enviar email de verificação"
        
        logger.info(f"Email de verificação reenviado com sucesso para: {user.email}")
        return True, "Email de verificação reenviado. Verifique sua caixa de entrada."
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao reenviar verificação: {str(e)}")
        return False, f"Erro ao reenviar verificação: {str(e)}"
    
    except Exception as e:
        logger.error(f"Erro inesperado ao reenviar verificação: {str(e)}")
        return False, f"Erro inesperado: {str(e)}"

def forgot_password(db: Session, email: str) -> Tuple[bool, str]:
    """
    Inicia o processo de recuperação de senha
    
    Args:
        db: Sessão do banco de dados
        email: Email do usuário
        
    Returns:
        Tuple[bool, str]: Tupla com status da operação e mensagem
    """
    try:
        # Buscar usuário pelo email
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            # Por segurança, não informamos se o email existe ou não
            logger.info(f"Tentativa de recuperação de senha para email inexistente: {email}")
            return True, "Se o email estiver cadastrado, você receberá instruções para redefinir sua senha."
        
        # Gerar token de reset
        reset_token = generate_token()
        token_expiry = datetime.utcnow() + timedelta(hours=1)  # Token válido por 1 hora
        
        # Atualizar usuário
        user.password_reset_token = reset_token
        user.password_reset_expiry = token_expiry
        
        db.commit()
        
        # Enviar email
        email_sent = send_password_reset_email(user.email, reset_token)
        if not email_sent:
            logger.error(f"Falha ao enviar email de recuperação de senha para {user.email}")
            return False, "Falha ao enviar email de recuperação de senha"
        
        logger.info(f"Email de recuperação de senha enviado com sucesso para: {user.email}")
        return True, "Se o email estiver cadastrado, você receberá instruções para redefinir sua senha."
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao processar recuperação de senha: {str(e)}")
        return False, f"Erro ao processar recuperação de senha: {str(e)}"
    
    except Exception as e:
        logger.error(f"Erro inesperado ao processar recuperação de senha: {str(e)}")
        return False, f"Erro inesperado: {str(e)}"

def reset_password(db: Session, token: str, new_password: str) -> Tuple[bool, str]:
    """
    Redefine a senha do usuário usando o token fornecido
    
    Args:
        db: Sessão do banco de dados
        token: Token de redefinição de senha
        new_password: Nova senha
        
    Returns:
        Tuple[bool, str]: Tupla com status da operação e mensagem
    """
    try:
        # Buscar usuário pelo token
        user = db.query(User).filter(User.password_reset_token == token).first()
        
        if not user:
            logger.warning(f"Tentativa de redefinição de senha com token inválido: {token}")
            return False, "Token de redefinição de senha inválido"
        
        # Verificar se o token expirou
        if user.password_reset_expiry < datetime.utcnow():
            logger.warning(f"Tentativa de redefinição de senha com token expirado para usuário: {user.email}")
            return False, "Token de redefinição de senha expirado"
        
        # Atualizar senha
        user.password_hash = get_password_hash(new_password)
        user.password_reset_token = None
        user.password_reset_expiry = None
        
        db.commit()
        logger.info(f"Senha redefinida com sucesso para usuário: {user.email}")
        return True, "Senha redefinida com sucesso. Você já pode fazer login com sua nova senha."
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao redefinir senha: {str(e)}")
        return False, f"Erro ao redefinir senha: {str(e)}"
    
    except Exception as e:
        logger.error(f"Erro inesperado ao redefinir senha: {str(e)}")
        return False, f"Erro inesperado: {str(e)}"

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Busca um usuário pelo email
    
    Args:
        db: Sessão do banco de dados
        email: Email do usuário
        
    Returns:
        Optional[User]: Usuário encontrado ou None
    """
    try:
        return db.query(User).filter(User.email == email).first()
    except Exception as e:
        logger.error(f"Erro ao buscar usuário por email: {str(e)}")
        return None

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Autentica um usuário com email e senha
    
    Args:
        db: Sessão do banco de dados
        email: Email do usuário
        password: Senha do usuário
        
    Returns:
        Optional[User]: Usuário autenticado ou None
    """
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user

def get_admin_users(db: Session, skip: int = 0, limit: int = 100):
    """
    Lista os usuários administradores
    
    Args:
        db: Sessão do banco de dados
        skip: Número de registros para pular
        limit: Número máximo de registros para retornar
        
    Returns:
        List[User]: Lista de usuários administradores
    """
    try:
        users = db.query(User).filter(User.is_admin == True).offset(skip).limit(limit).all()
        logger.info(f"Listagem de administradores: {len(users)} encontrados")
        return users
        
    except SQLAlchemyError as e:
        logger.error(f"Erro ao listar administradores: {str(e)}")
        return []
    
    except Exception as e:
        logger.error(f"Erro inesperado ao listar administradores: {str(e)}")
        return []

def create_admin_user(db: Session, user_data: UserCreate) -> Tuple[Optional[User], str]:
    """
    Cria um novo usuário administrador
    
    Args:
        db: Sessão do banco de dados
        user_data: Dados do usuário a ser criado
        
    Returns:
        Tuple[Optional[User], str]: Tupla com o usuário criado (ou None em caso de erro) e mensagem de status
    """
    return create_user(db, user_data, is_admin=True)

def deactivate_user(db: Session, user_id: uuid.UUID) -> Tuple[bool, str]:
    """
    Desativa um usuário (não exclui, apenas marca como inativo)
    
    Args:
        db: Sessão do banco de dados
        user_id: ID do usuário a ser desativado
        
    Returns:
        Tuple[bool, str]: Tupla com status da operação e mensagem
    """
    try:
        # Buscar usuário pelo ID
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            logger.warning(f"Tentativa de desativação de usuário inexistente: {user_id}")
            return False, "Usuário não encontrado"
        
        # Desativar usuário
        user.is_active = False
        
        db.commit()
        logger.info(f"Usuário desativado com sucesso: {user.email}")
        return True, "Usuário desativado com sucesso"
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Erro ao desativar usuário: {str(e)}")
        return False, f"Erro ao desativar usuário: {str(e)}"
    
    except Exception as e:
        logger.error(f"Erro inesperado ao desativar usuário: {str(e)}")
        return False, f"Erro inesperado: {str(e)}" 