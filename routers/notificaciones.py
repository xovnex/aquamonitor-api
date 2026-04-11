# ============================================================
# routers/notificaciones.py – Email (Resend) y WhatsApp
# ============================================================
import os
import random
import string
import resend
from twilio.rest import Client

resend.api_key     = os.getenv("RESEND_API_KEY")
TWILIO_SID         = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN       = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER      = os.getenv("TWILIO_WHATSAPP_NUMBER")

def generar_codigo():
    return ''.join(random.choices(string.digits, k=6))

def enviar_email(destinatario: str, asunto: str, cuerpo_html: str):
    try:
        resend.Emails.send({
            "from": "AquaMonitor <onboarding@resend.dev>",
            "to": destinatario,
            "subject": asunto,
            "html": cuerpo_html,
        })
        return True
    except Exception as e:
        print(f"Error enviando email: {e}")
        return False

def enviar_codigo_verificacion(email: str, codigo: str):
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
    mensaje = f"""⚠️ *AquaMonitor - Alerta de consumo*

Has superado tu límite diario de agua.

💧 Consumo actual: *{litros:.1f} L*
🎯 Tu límite: *{limite:.1f} L*
📊 Excedente: *{litros - limite:.1f} L*

Reduce tu consumo para cuidar el planeta 🌍"""
    return enviar_whatsapp_alerta(telefono, mensaje)

def alerta_fuga_detectada(telefono: str, flujo: float):
    mensaje = f"""🚨 *AquaMonitor - Posible fuga detectada*

Se detectó flujo constante inusual en tu sistema.

💧 Flujo actual: *{flujo:.2f} L/min*

Revisa tus cañerías urgentemente 🔧"""
    return enviar_whatsapp_alerta(telefono, mensaje)