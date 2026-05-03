# ============================================================
# routers/consumo.py – Endpoints de consumo + alertas
# ============================================================
from fastapi import APIRouter, HTTPException, Header
from datetime import date, timedelta
from database import get_connection, release_connection
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
        "SELECT limite_diario, personas, notificaciones, alerta_fuga FROM configuraciones WHERE usuario_id = %s",
        (usuario_id,)
    )
    cfg = cur.fetchone()
    return cfg if cfg else (200, 3, True, True)

def get_telefono(cur, usuario_id):
    cur.execute("SELECT telefono FROM usuarios WHERE id = %s", (usuario_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None

@router.get("/hoy")
def consumo_hoy(authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cfg = get_config(cur, usuario_id)
        limite, personas = cfg[0], cfg[1]
        hoy = date.today()
        cur.execute(
            "SELECT litros, flujo_actual, temperatura_agua FROM consumos WHERE usuario_id = %s AND fecha = %s",
            (usuario_id, hoy)
        )
        row = cur.fetchone()
        return {
            "fecha": str(hoy),
            "litros": round(row[0], 2) if row else 0,
            "limite": limite,
            "personas": personas,
            "flujoActual": round(row[1], 2) if row else 0,
            "temperaturaAgua": row[2] if row else 18,
            "sensor": {
                "id": "ESP32-001",
                "estado": "online",
                "bateria": 87,
                "ultimaActualizacion": str(hoy)
            }
        }
    finally:
        cur.close()
        release_connection(conn)

@router.get("/semanal")
def consumo_semanal(authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cfg = get_config(cur, usuario_id)
        limite = cfg[0]
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
        return resultado
    finally:
        cur.close()
        release_connection(conn)

@router.get("/mensual")
def consumo_mensual(authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cfg = get_config(cur, usuario_id)
        limite = cfg[0]
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
        return resultado
    finally:
        cur.close()
        release_connection(conn)

@router.post("/sensor")
def recibir_sensor(data: SensorData, authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    conn = get_connection()
    cur  = conn.cursor()
    try:
        hoy = date.today()
        cur.execute("""
            INSERT INTO consumos (usuario_id, fecha, litros, flujo_actual, temperatura_agua)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (usuario_id, fecha)
            DO UPDATE SET
                litros = ROUND((consumos.litros + EXCLUDED.litros)::numeric, 2),
                flujo_actual = ROUND(EXCLUDED.flujo_actual::numeric, 2),
                temperatura_agua = EXCLUDED.temperatura_agua
        """, (usuario_id, hoy, data.litros, data.flujo_actual, data.temperatura_agua))
        

        cfg = get_config(cur, usuario_id)
        limite         = cfg[0]
        notificaciones = cfg[2]
        alerta_fuga    = cfg[3]

        cur.execute(
            "SELECT litros, ultima_alerta_consumo, ultima_alerta_fuga FROM consumos WHERE usuario_id = %s AND fecha = %s",
            (usuario_id, hoy)
        )
        row = cur.fetchone()
        litros_total        = row[0] if row else 0
        ultima_alerta_consumo = row[1] if row else None
        ultima_alerta_fuga    = row[2] if row else None

        telefono = get_telefono(cur, usuario_id)
        conn.commit()

        from datetime import datetime, timedelta
        ahora = datetime.utcnow()

        if telefono:
            # Alerta consumo — solo si pasó más de 1 hora desde la última
            if notificaciones and litros_total > limite:
                if not ultima_alerta_consumo or ahora - ultima_alerta_consumo > timedelta(hours=1):
                    alerta_consumo_alto(telefono, litros_total, limite)
                    cur2 = conn.cursor()
                    cur2.execute(
                        "UPDATE consumos SET ultima_alerta_consumo = %s WHERE usuario_id = %s AND fecha = %s",
                        (ahora, usuario_id, hoy)
                    )
                    conn.commit()
                    cur2.close()

            # Alerta fuga — solo si pasó más de 1 hora desde la última
            if alerta_fuga and data.flujo_actual > 10:
                if not ultima_alerta_fuga or ahora - ultima_alerta_fuga > timedelta(hours=1):
                    alerta_fuga_detectada(telefono, data.flujo_actual)
                    cur3 = conn.cursor()
                    cur3.execute(
                        "UPDATE consumos SET ultima_alerta_fuga = %s WHERE usuario_id = %s AND fecha = %s",
                        (ahora, usuario_id, hoy)
                    )
                    conn.commit()
                    cur3.close()

        return {"success": True, "message": "Datos recibidos"}
    finally:
        cur.close()
        release_connection(conn)