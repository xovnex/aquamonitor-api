# ============================================================
# routers/consumo.py – Endpoints de consumo + alertas
# ============================================================
from fastapi import APIRouter, HTTPException, Header
from datetime import date, timedelta
from database import get_connection
from routers.auth import verificar_token
from routers.notificaciones import alerta_consumo_alto, alerta_fuga_detectada
from schemas import SensorData

router = APIRouter(prefix="/consumo", tags=["consumo"])

DIAS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

def get_user_id(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization.split(" ")[1]
    payload = verificar_token(token)
    return int(payload["sub"])

def get_config(cur, usuario_id):
    cur.execute(
        "SELECT limite_diario, personas FROM configuraciones WHERE usuario_id = %s",
        (usuario_id,)
    )
    cfg = cur.fetchone()
    return cfg if cfg else (200, 3)

def get_telefono(cur, usuario_id):
    cur.execute("SELECT telefono FROM usuarios WHERE id = %s", (usuario_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None

@router.get("/hoy")
def consumo_hoy(authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    conn = get_connection()
    cur  = conn.cursor()

    limite, personas = get_config(cur, usuario_id)
    hoy = date.today()

    cur.execute(
        "SELECT litros, flujo_actual, temperatura_agua FROM consumos WHERE usuario_id = %s AND fecha = %s",
        (usuario_id, hoy)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    litros = row[0] if row else 0
    flujo  = row[1] if row else 0
    temp   = row[2] if row else 18

    return {
        "fecha": str(hoy),
        "litros": litros,
        "limite": limite,
        "personas": personas,
        "flujoActual": flujo,
        "temperaturaAgua": temp,
        "sensor": {
            "id": "ESP32-001",
            "estado": "online",
            "bateria": 87,
            "ultimaActualizacion": str(hoy)
        }
    }

@router.get("/semanal")
def consumo_semanal(authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    conn = get_connection()
    cur  = conn.cursor()

    limite, _ = get_config(cur, usuario_id)
    hoy = date.today()

    resultado = []
    for i in range(6, -1, -1):
        dia = hoy - timedelta(days=i)
        cur.execute(
            "SELECT litros FROM consumos WHERE usuario_id = %s AND fecha = %s",
            (usuario_id, dia)
        )
        row = cur.fetchone()
        resultado.append({
            "dia": DIAS_ES[dia.weekday()],
            "litros": row[0] if row else 0,
            "limite": limite
        })

    cur.close()
    conn.close()
    return resultado

@router.get("/mensual")
def consumo_mensual(authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    conn = get_connection()
    cur  = conn.cursor()

    limite, _ = get_config(cur, usuario_id)
    hoy = date.today()

    resultado = []
    for i in range(29, -1, -1):
        dia = hoy - timedelta(days=i)
        cur.execute(
            "SELECT litros FROM consumos WHERE usuario_id = %s AND fecha = %s",
            (usuario_id, dia)
        )
        row = cur.fetchone()
        resultado.append({
            "fecha": str(dia),
            "litros": row[0] if row else 0,
            "limite": limite
        })

    cur.close()
    conn.close()
    return resultado

@router.post("/sensor")
def recibir_sensor(data: SensorData, authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    conn = get_connection()
    cur  = conn.cursor()
    hoy  = date.today()

    cur.execute("""
        INSERT INTO consumos (usuario_id, fecha, litros, flujo_actual, temperatura_agua)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (usuario_id, fecha)
        DO UPDATE SET
            litros = consumos.litros + EXCLUDED.litros,
            flujo_actual = EXCLUDED.flujo_actual,
            temperatura_agua = EXCLUDED.temperatura_agua
    """, (usuario_id, hoy, data.litros, data.flujo_actual, data.temperatura_agua))

    # Verificar si supera el límite para mandar alerta
    limite, _ = get_config(cur, usuario_id)
    cur.execute(
        "SELECT litros FROM consumos WHERE usuario_id = %s AND fecha = %s",
        (usuario_id, hoy)
    )
    row = cur.fetchone()
    litros_total = row[0] if row else 0

    telefono = get_telefono(cur, usuario_id)

    conn.commit()
    cur.close()
    conn.close()

    # Mandar alerta WhatsApp si supera límite
    if telefono and litros_total > limite:
        alerta_consumo_alto(telefono, litros_total, limite)

    # Mandar alerta si detecta fuga (flujo > 2.5 L/min)
    if telefono and data.flujo_actual > 2.5:
        alerta_fuga_detectada(telefono, data.flujo_actual)

    return {"success": True, "message": "Datos recibidos"}