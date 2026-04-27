# ============================================================
# routers/analisis.py – Análisis inteligente con Groq (gratis)
# ============================================================
from fastapi import APIRouter, Header, HTTPException
from datetime import date, timedelta
from database import get_connection
from routers.auth import verificar_token
from groq import Groq
from pydantic import BaseModel
import os

router = APIRouter(prefix="/analisis", tags=["analisis"])

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def get_user_id(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization.split(" ")[1]
    payload = verificar_token(token)
    return int(payload["sub"])


@router.get("/semanal")
def analisis_semanal(authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    conn = get_connection()
    cur = conn.cursor()
    hoy = date.today()

    datos_semana = []
    for i in range(6, -1, -1):
        dia = hoy - timedelta(days=i)
        cur.execute(
            "SELECT litros FROM consumos WHERE usuario_id = %s AND fecha = %s",
            (usuario_id, dia)
        )
        row = cur.fetchone()
        datos_semana.append({
            "fecha": str(dia),
            "dia": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][dia.weekday()],
            "litros": round(row[0], 2) if row else 0
        })

    cur.execute(
        "SELECT limite_diario, personas FROM configuraciones WHERE usuario_id = %s",
        (usuario_id,)
    )
    cfg = cur.fetchone()
    limite = cfg[0] if cfg else 200
    personas = cfg[1] if cfg else 1

    cur.close()
    conn.close()

    total = sum(d["litros"] for d in datos_semana)
    promedio = round(total / 7, 2)
    max_dia = max(datos_semana, key=lambda x: x["litros"])
    min_dia = min(datos_semana, key=lambda x: x["litros"])
    dias_excedidos = [d for d in datos_semana if d["litros"] > limite]

    prompt = f"""
Eres un asistente experto en ahorro de agua para hogares. Analiza el siguiente consumo semanal de agua y da un análisis claro, útil y motivador en español.
Sé conciso (máximo 4 oraciones). No uses listas ni bullet points, solo párrafos cortos.

Datos del usuario:
- Límite diario configurado: {limite} litros
- Personas en el hogar: {personas}
- Consumo por día esta semana: {datos_semana}
- Total semanal: {total} litros
- Promedio diario: {promedio} litros
- Día de mayor consumo: {max_dia['dia']} con {max_dia['litros']} litros
- Día de menor consumo: {min_dia['dia']} con {min_dia['litros']} litros
- Días que superaron el límite: {len(dias_excedidos)}

Analiza si el consumo es bueno o malo, explica por qué, menciona el día más destacado y da una recomendación práctica.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7,
        )
        analisis = response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error con Groq: {str(e)}")

    return {
        "analisis": analisis,
        "datos": {
            "total": total,
            "promedio": promedio,
            "max_dia": max_dia,
            "min_dia": min_dia,
            "dias_excedidos": len(dias_excedidos),
            "limite": limite,
        }
    }


# ============================================================
# POST /analisis/chat
# ============================================================
class PreguntaChat(BaseModel):
    pregunta: str
    contexto: dict


@router.post("/chat")
def chat_analisis(data: PreguntaChat, authorization: str = Header(None)):
    get_user_id(authorization)

    prompt = f"""
Eres un asistente experto en ahorro y consumo de agua dentro de la app AquaMonitor.

Tu ÚNICA función es responder preguntas relacionadas con:
- Consumo de agua del usuario
- Ahorro de agua en el hogar
- Análisis semanal de consumo
- Alertas y límites configurados
- Predicciones de consumo
- Recomendaciones sobre el proyecto AquaMonitor
- Configuración del hogar (personas, límite diario)

Contexto actual del análisis del usuario:
{data.contexto}

Pregunta del usuario:
{data.pregunta}

REGLA IMPORTANTE:
Si la pregunta NO está relacionada con consumo de agua, ahorro hídrico o el proyecto AquaMonitor,
responde EXACTAMENTE: "Solo puedo ayudarte con preguntas relacionadas con tu consumo de agua y el proyecto AquaMonitor."

Si sí está relacionada, responde de forma clara, breve (máximo 3 oraciones) y útil en español.
No uses listas ni bullet points, solo texto corrido.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.6,
        )
        respuesta = response.choices[0].message.content.strip()
        return {"respuesta": respuesta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error con Groq: {str(e)}")