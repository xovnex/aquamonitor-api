# ============================================================
# routers/consumo.py – Endpoints de consumo + alertas
# ============================================================
from fastapi import APIRouter, HTTPException, Header
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from datetime import datetime
from database import get_db
from routers.auth import verificar_token
from routers.notificaciones import alerta_consumo_alto, alerta_fuga_detectada
from schemas import SensorData

router = APIRouter(prefix="/consumo", tags=["consumo"])

LIMA_TZ = ZoneInfo("America/Lima")
DIAS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
DEFAULT_COSTO_POR_LITRO = 0.005
SENSOR_TIMEOUT_SEC = 180

def hoy_lima() -> date:
    """Retorna la fecha actual en zona horaria de Lima (UTC-5)."""
    return datetime.now(LIMA_TZ).date()

def get_user_id(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization.split(" ")[1]
    payload = verificar_token(token)
    return int(payload["sub"])

def get_config(cur, usuario_id):
    cur.execute(
        """
        SELECT limite_diario, personas, notificaciones, alerta_fuga, costo_por_litro
        FROM configuraciones WHERE usuario_id = %s
        """,
        (usuario_id,),
    )
    cfg = cur.fetchone()
    if cfg:
        costo = cfg[4] if cfg[4] is not None else DEFAULT_COSTO_POR_LITRO
        return (cfg[0], cfg[1], cfg[2], cfg[3], costo)
    return (200, 3, True, True, DEFAULT_COSTO_POR_LITRO)

def get_telefono(cur, usuario_id):
    cur.execute("SELECT telefono FROM usuarios WHERE id = %s", (usuario_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None

def evaluar_sensor(ultima_lectura):
    """En línea solo si el ESP32 envió datos en los últimos N segundos."""
    if ultima_lectura is None:
        return False, None, None

    if ultima_lectura.tzinfo is None:
        ultima = ultima_lectura.replace(tzinfo=LIMA_TZ)
    else:
        ultima = ultima_lectura.astimezone(LIMA_TZ)

    ahora = datetime.now(LIMA_TZ)
    diff = (ahora - ultima).total_seconds()
    en_linea = 0 <= diff <= SENSOR_TIMEOUT_SEC
    return en_linea, ultima.isoformat(), int(diff)

@router.get("/hoy")
def consumo_hoy(authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    with get_db() as conn:
        cur = conn.cursor()
        cfg = get_config(cur, usuario_id)
        limite, personas, _, _, costo_por_litro = cfg
        hoy = hoy_lima()
        cur.execute(
            "SELECT litros, flujo_actual, temperatura_agua, ultima_lectura FROM consumos WHERE usuario_id = %s AND fecha = %s",
            (usuario_id, hoy),
        )
        row = cur.fetchone()
        ultima_raw = row[3] if row else None
        en_linea, ultima_lectura, segundos_sin_datos = evaluar_sensor(ultima_raw)
        litros = round(row[0], 2) if row else 0
        flujo = round(row[1], 2) if row and en_linea else 0
        costo_estimado = round(litros * costo_por_litro, 2)
        cur.close()
        return {
            "fecha": str(hoy),
            "litros": litros,
            "limite": limite,
            "personas": personas,
            "costo_por_litro": costo_por_litro,
            "costo_estimado": costo_estimado,
            "flujoActual": flujo,
            "temperaturaAgua": row[2] if row else 18,
            "sensor": {
                "id": "ESP32-001",
                "enLinea": en_linea,
                "ultimaLectura": ultima_lectura,
                "segundosSinDatos": segundos_sin_datos,
            },
        }

@router.get("/semanal")
def consumo_semanal(authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    with get_db() as conn:
        cur = conn.cursor()
        cfg = get_config(cur, usuario_id)
        limite = cfg[0]
        hoy = hoy_lima()
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
        return resultado

@router.get("/mensual")
def consumo_mensual(authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    with get_db() as conn:
        cur = conn.cursor()
        cfg = get_config(cur, usuario_id)
        limite = cfg[0]
        hoy = hoy_lima()
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
        return resultado

@router.post("/sensor")
def recibir_sensor(data: SensorData, authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    with get_db() as conn:
        cur = conn.cursor()
        hoy = hoy_lima()
        cur.execute("""
            INSERT INTO consumos (usuario_id, fecha, litros, flujo_actual, temperatura_agua, ultima_lectura)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (usuario_id, fecha)
            DO UPDATE SET
                litros = ROUND((consumos.litros + EXCLUDED.litros)::numeric, 2),
                flujo_actual = ROUND(EXCLUDED.flujo_actual::numeric, 2),
                temperatura_agua = EXCLUDED.temperatura_agua,
                ultima_lectura = NOW()
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
        litros_total          = row[0] if row else 0
        ultima_alerta_consumo = row[1] if row else None
        ultima_alerta_fuga    = row[2] if row else None

        telefono = get_telefono(cur, usuario_id)
        conn.commit()

        from datetime import datetime, timedelta
        ahora = datetime.now(LIMA_TZ)

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

        cur.close()
        return {"success": True, "message": "Datos recibidos"}