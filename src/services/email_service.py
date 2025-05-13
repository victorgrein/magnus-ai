"""
┌──────────────────────────────────────────────────────────────────────────────┐
│ @author: Davidson Gomes                                                      │
│ @file: email_service.py                                                      │
│ Developed by: Davidson Gomes                                                 │
│ Creation date: May 13, 2025                                                  │
│ Contact: contato@evolution-api.com                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│ @copyright © Evolution API 2025. All rights reserved.                        │
│ Licensed under the Apache License, Version 2.0                               │
│                                                                              │
│ You may not use this file except in compliance with the License.             │
│ You may obtain a copy of the License at                                      │
│                                                                              │
│    http://www.apache.org/licenses/LICENSE-2.0                                │
│                                                                              │
│ Unless required by applicable law or agreed to in writing, software          │
│ distributed under the License is distributed on an "AS IS" BASIS,            │
│ WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.     │
│ See the License for the specific language governing permissions and          │
│ limitations under the License.                                               │
├──────────────────────────────────────────────────────────────────────────────┤
│ @important                                                                   │
│ For any future changes to the code in this file, it is recommended to        │
│ include, together with the modification, the information of the developer    │
│ who changed it and the date of modification.                                 │
└──────────────────────────────────────────────────────────────────────────────┘
"""

import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
import logging
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Configure Jinja2 to load templates
templates_dir = Path(__file__).parent.parent / "templates" / "emails"
os.makedirs(templates_dir, exist_ok=True)

# Configure Jinja2 with the templates directory
env = Environment(
    loader=FileSystemLoader(templates_dir),
    autoescape=select_autoescape(["html", "xml"]),
)


def _render_template(template_name: str, context: dict) -> str:
    """
    Render a template with the provided data

    Args:
        template_name: Template file name
        context: Data to render in the template

    Returns:
        str: Rendered HTML
    """
    try:
        template = env.get_template(f"{template_name}.html")
        return template.render(**context)
    except Exception as e:
        logger.error(f"Error rendering template '{template_name}': {str(e)}")
        return f"<p>Could not display email content. Please access {context.get('verification_link', '') or context.get('reset_link', '')}</p>"


def send_verification_email(email: str, token: str) -> bool:
    """
    Send a verification email to the user

    Args:
        email: Recipient's email
        token: Email verification token

    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
        from_email = Email(os.getenv("EMAIL_FROM"))
        to_email = To(email)
        subject = "Email Verification - Evo AI"

        verification_link = f"{os.getenv('APP_URL')}/security/verify-email?code={token}"

        html_content = _render_template(
            "verification_email",
            {
                "verification_link": verification_link,
                "user_name": email.split("@")[
                    0
                ],  # Use part of the email as temporary name
                "current_year": datetime.now().year,
            },
        )

        content = Content("text/html", html_content)

        mail = Mail(from_email, to_email, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())

        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Verification email sent to {email}")
            return True
        else:
            logger.error(
                f"Failed to send verification email to {email}. Status: {response.status_code}"
            )
            return False

    except Exception as e:
        logger.error(f"Error sending verification email to {email}: {str(e)}")
        return False


def send_password_reset_email(email: str, token: str) -> bool:
    """
    Send a password reset email to the user

    Args:
        email: Recipient's email
        token: Password reset token

    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
        from_email = Email(os.getenv("EMAIL_FROM"))
        to_email = To(email)
        subject = "Password Reset - Evo AI"

        reset_link = f"{os.getenv('APP_URL')}/security/reset-password?token={token}"

        html_content = _render_template(
            "password_reset",
            {
                "reset_link": reset_link,
                "user_name": email.split("@")[
                    0
                ],  # Use part of the email as temporary name
                "current_year": datetime.now().year,
            },
        )

        content = Content("text/html", html_content)

        mail = Mail(from_email, to_email, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())

        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Password reset email sent to {email}")
            return True
        else:
            logger.error(
                f"Failed to send password reset email to {email}. Status: {response.status_code}"
            )
            return False

    except Exception as e:
        logger.error(f"Error sending password reset email to {email}: {str(e)}")
        return False


def send_welcome_email(email: str, user_name: str = None) -> bool:
    """
    Send a welcome email to the user after verification

    Args:
        email: Recipient's email
        user_name: User's name (optional)

    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
        from_email = Email(os.getenv("EMAIL_FROM"))
        to_email = To(email)
        subject = "Welcome to Evo AI"

        dashboard_link = f"{os.getenv('APP_URL')}/dashboard"

        html_content = _render_template(
            "welcome_email",
            {
                "dashboard_link": dashboard_link,
                "user_name": user_name or email.split("@")[0],
                "current_year": datetime.now().year,
            },
        )

        content = Content("text/html", html_content)

        mail = Mail(from_email, to_email, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())

        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Welcome email sent to {email}")
            return True
        else:
            logger.error(
                f"Failed to send welcome email to {email}. Status: {response.status_code}"
            )
            return False

    except Exception as e:
        logger.error(f"Error sending welcome email to {email}: {str(e)}")
        return False


def send_account_locked_email(
    email: str, reset_token: str, failed_attempts: int, time_period: str
) -> bool:
    """
    Send an email informing that the account has been locked after login attempts

    Args:
        email: Recipient's email
        reset_token: Token to reset the password
        failed_attempts: Number of failed attempts
        time_period: Time period of the attempts

    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
        from_email = Email(os.getenv("EMAIL_FROM"))
        to_email = To(email)
        subject = "Security Alert - Account Locked"

        reset_link = (
            f"{os.getenv('APP_URL')}/security/reset-password?token={reset_token}"
        )

        html_content = _render_template(
            "account_locked",
            {
                "reset_link": reset_link,
                "user_name": email.split("@")[0],
                "failed_attempts": failed_attempts,
                "time_period": time_period,
                "current_year": datetime.now().year,
            },
        )

        content = Content("text/html", html_content)

        mail = Mail(from_email, to_email, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())

        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Account locked email sent to {email}")
            return True
        else:
            logger.error(
                f"Failed to send account locked email to {email}. Status: {response.status_code}"
            )
            return False

    except Exception as e:
        logger.error(f"Error sending account locked email to {email}: {str(e)}")
        return False
