from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import EmailStr
from pathlib import Path
import os
from .auth_utils import create_access_token
from datetime import timedelta

# Configurações de Email (Hardcoded como solicitado)
conf = ConnectionConfig(
    MAIL_USERNAME = "noreplytust@gmail.com",
    MAIL_PASSWORD = "xldu yjsp svdq kzae",
    MAIL_FROM = "noreplytust@gmail.com",
    MAIL_PORT = 587,
    MAIL_SERVER = "smtp.gmail.com",
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

async def send_confirmation_email(email_to: EmailStr, username: str, password: str = None):
    token = create_access_token(
        data={"sub": username, "scope": "email_confirmation", "email": email_to},
        expires_delta=timedelta(hours=24)
    )
    
    confirm_url = f"http://localhost:8000/confirmar-email?token={token}"
    
    password_html = ""
    if password:
        password_html = f"""
        <div style="background-color: #e2e8f0; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center;">
            <p style="margin: 0; color: #475569; font-size: 0.9em;">Sua senha temporária:</p>
            <p style="margin: 5px 0 0 0; color: #1e293b; font-weight: bold; font-size: 1.2em; font-family: monospace;">{password}</p>
        </div>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h2 style="color: #3b82f6; text-align: center;">Bem-vindo ao Tust-AETE Robo Runner! 🤖</h2>
                <p>Olá <strong>{username}</strong>,</p>
                <p>Sua conta foi criada com sucesso.</p>
                
                {password_html}

                <p>Para ativar e confirmar seu email, por favor clique no botão abaixo:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{confirm_url}" 
                       style="background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                       ✅ Confirmar Email
                    </a>
                </div>
                
                <p style="font-size: 0.8em; color: #666; text-align: center;">
                    Este link é válido por 24 horas.<br>
                    Se você não solicitou este acesso, apenas ignore este email.
                </p>
            </div>
        </body>
    </html>
    """

    message = MessageSchema(
        subject="Confirme seu cadastro - AETE Robo Runner",
        recipients=[email_to],
        body=html,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    await fm.send_message(message)
    print(f"📧 Email de confirmação enviado para {email_to}")
