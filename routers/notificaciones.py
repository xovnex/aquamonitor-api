# ============================================================
# routers/notificaciones.py – Email y WhatsApp
# ============================================================
import smtplib
import os
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client

GMAIL_USER     = os.getenv("GMAIL_USER")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
TWILIO_SID     = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER  = os.getenv("TWILIO_WHATSAPP_NUMBER")

def generar_codigo():
    """Genera código de 6 dígitos"""
    return ''.join(random.choices(string.digits, k=6))

def enviar_email(destinatario: str, asunto: str, cuerpo_html: str):
    """Envía email via Gmail"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"]    = f"AquaMonitor 💧 <{GMAIL_USER}>"
        msg["To"]      = destinatario

        parte = MIMEText(cuerpo_html, "html")
        msg.attach(parte)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, destinatario, msg.as_string())

        return True
    except Exception as e:
        print(f"Error enviando email: {e}")
        return False

def enviar_codigo_verificacion(email: str, codigo: str):
    """Email de verificación al registrarse"""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; background: #060d1a; color: #e2f0ff; padding: 30px; border-radius: 16px;">
        <h2 style="color: #1eb8f0; text-align: center;">💧 AquaMonitor</h2>
        <h3 style="text-align: center;">Verificación de cuenta</h3>
        <p>Gracias por registrarte. Usa este código para verificar tu cuenta:</p>
        <div style="background: #0a1628; border: 2px solid #1eb8f0; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0;">
            <span style="font-size: 36px; font-weight: bold; color: #1eb8f0; letter-spacing: 8px;">{codigo}</span>
        </div>
        <p style="color: rgba(255,255,255,0.5); font-size: 12px;">Este código expira en 10 minutos.</p>
    </div>
    """
    return enviar_email(email, "💧 AquaMonitor – Verifica tu cuenta", html)

def enviar_codigo_reset(email: str, codigo: str):
    """Email para recuperar contraseña"""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; background: #060d1a; color: #e2f0ff; padding: 30px; border-radius: 16px;">
        <h2 style="color: #1eb8f0; text-align: center;">💧 AquaMonitor</h2>
        <h3 style="text-align: center;">Recuperar contraseña</h3>
        <p>Recibimos una solicitud para restablecer tu contraseña. Usa este código:</p>
        <div style="background: #0a1628; border: 2px solid #f59e0b; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0;">
            <span style="font-size: 36px; font-weight: bold; color: #f59e0b; letter-spacing: 8px;">{codigo}</span>
        </div>
        <p style="color: rgba(255,255,255,0.5); font-size: 12px;">Si no solicitaste esto, ignora este correo. Expira en 10 minutos.</p>
    </div>
    """
    return enviar_email(email, "💧 AquaMonitor – Recuperar contraseña", html)

def enviar_whatsapp_alerta(telefono: str, mensaje: str):
    """Envía alerta por WhatsApp via Twilio"""
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(
            body=mensaje,
            from_=f"whatsapp:{TWILIO_NUMBER}",
            to=f"whatsapp:{telefono}"
        )
        return True
    except Exception as e:
        print(f"Error enviando WhatsApp: {e}")
        return False

def alerta_consumo_alto(telefono: str, litros: float, limite: float):
    """Alerta cuando supera el límite"""
    mensaje = f"""⚠️ *AquaMonitor - Alerta de consumo*

Has superado tu límite diario de agua.

💧 Consumo actual: *{litros:.1f} L*
🎯 Tu límite: *{limite:.1f} L*
📊 Excedente: *{litros - limite:.1f} L*

Reduce tu consumo para cuidar el planeta 🌍"""
    return enviar_whatsapp_alerta(telefono, mensaje)

def alerta_fuga_detectada(telefono: str, flujo: float):
    """Alerta cuando se detecta posible fuga"""
    mensaje = f"""🚨 *AquaMonitor - Posible fuga detectada*

Se detectó flujo constante inusual en tu sistema.

💧 Flujo actual: *{flujo:.2f} L/min*

Revisa tus cañerías urgentemente 🔧"""
    return enviar_whatsapp_alerta(telefono, mensaje)