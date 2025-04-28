import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from src.config.settings import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def send_verification_email(email: str, token: str) -> bool:
    """
    Envia um email de verificação para o usuário
    
    Args:
        email: Email do destinatário
        token: Token de verificação de email
        
    Returns:
        bool: True se o email foi enviado com sucesso, False caso contrário
    """
    try:
        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        from_email = Email(settings.EMAIL_FROM)
        to_email = To(email)
        subject = "Verificação de Email - Evo AI"
        
        verification_link = f"{settings.APP_URL}/auth/verify-email/{token}"
        
        content = Content(
            "text/html", 
            f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4A90E2; color: white; padding: 10px; text-align: center; }}
                    .content {{ padding: 20px; }}
                    .button {{ background-color: #4A90E2; color: white; padding: 10px 20px; 
                              text-decoration: none; border-radius: 4px; display: inline-block; }}
                    .footer {{ font-size: 12px; text-align: center; margin-top: 30px; color: #888; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Evo AI</h1>
                    </div>
                    <div class="content">
                        <h2>Bem-vindo à Plataforma Evo AI!</h2>
                        <p>Obrigado por se cadastrar. Para verificar sua conta e começar a usar nossos serviços, 
                           por favor clique no botão abaixo:</p>
                        <p style="text-align: center;">
                            <a href="{verification_link}" class="button">Verificar meu Email</a>
                        </p>
                        <p>Ou copie e cole o link abaixo no seu navegador:</p>
                        <p>{verification_link}</p>
                        <p>Este link é válido por 24 horas.</p>
                        <p>Se você não solicitou este email, por favor ignore-o.</p>
                    </div>
                    <div class="footer">
                        <p>Este é um email automático, por favor não responda.</p>
                        <p>&copy; {datetime.now().year} Evo AI. Todos os direitos reservados.</p>
                    </div>
                </div>
            </body>
            </html>
            """
        )
        
        mail = Mail(from_email, to_email, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())
        
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Email de verificação enviado para {email}")
            return True
        else:
            logger.error(f"Falha ao enviar email de verificação para {email}. Status: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Erro ao enviar email de verificação para {email}: {str(e)}")
        return False

def send_password_reset_email(email: str, token: str) -> bool:
    """
    Envia um email de redefinição de senha para o usuário
    
    Args:
        email: Email do destinatário
        token: Token de redefinição de senha
        
    Returns:
        bool: True se o email foi enviado com sucesso, False caso contrário
    """
    try:
        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        from_email = Email(settings.EMAIL_FROM)
        to_email = To(email)
        subject = "Redefinição de Senha - Evo AI"
        
        reset_link = f"{settings.APP_URL}/reset-password?token={token}"
        
        content = Content(
            "text/html", 
            f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4A90E2; color: white; padding: 10px; text-align: center; }}
                    .content {{ padding: 20px; }}
                    .button {{ background-color: #4A90E2; color: white; padding: 10px 20px; 
                              text-decoration: none; border-radius: 4px; display: inline-block; }}
                    .footer {{ font-size: 12px; text-align: center; margin-top: 30px; color: #888; }}
                    .warning {{ color: #E74C3C; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Evo AI</h1>
                    </div>
                    <div class="content">
                        <h2>Redefinição de Senha</h2>
                        <p>Recebemos uma solicitação para redefinir sua senha. Clique no botão abaixo 
                           para criar uma nova senha:</p>
                        <p style="text-align: center;">
                            <a href="{reset_link}" class="button">Redefinir minha Senha</a>
                        </p>
                        <p>Ou copie e cole o link abaixo no seu navegador:</p>
                        <p>{reset_link}</p>
                        <p>Este link é válido por 1 hora.</p>
                        <p class="warning">Se você não solicitou esta alteração, por favor ignore este email 
                           e entre em contato com o suporte imediatamente.</p>
                    </div>
                    <div class="footer">
                        <p>Este é um email automático, por favor não responda.</p>
                        <p>&copy; {datetime.now().year} Evo AI. Todos os direitos reservados.</p>
                    </div>
                </div>
            </body>
            </html>
            """
        )
        
        mail = Mail(from_email, to_email, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())
        
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Email de redefinição de senha enviado para {email}")
            return True
        else:
            logger.error(f"Falha ao enviar email de redefinição de senha para {email}. Status: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Erro ao enviar email de redefinição de senha para {email}: {str(e)}")
        return False 