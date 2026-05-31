# ============================================================
# routers/configuracion.py – Configuración del usuario
# ============================================================
from fastapi import APIRouter, Header, HTTPException
from database import get_db
from routers.auth import verificar_token
from schemas import ConfiguracionUpdate, ConfiguracionResponse

router = APIRouter(tags=["configuracion"])

DEFAULT_COSTO_POR_LITRO = 0.005

def to_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def get_user_id(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization.split(" ")[1]
    payload = verificar_token(token)
    return int(payload["sub"])

def fetch_config_row(cur, usuario_id):
    cur.execute(
        """
        SELECT limite_diario, personas, notificaciones, alerta_fuga, costo_por_litro
        FROM configuraciones
        WHERE usuario_id = %s
        """,
        (usuario_id,),
    )
    return cur.fetchone()

@router.get("/configuracion", response_model=ConfiguracionResponse)
def obtener_configuracion(authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    with get_db() as conn:
        cur = conn.cursor()
        row = fetch_config_row(cur, usuario_id)
        cur.close()

    if not row:
        return ConfiguracionResponse(
            limite_diario=200,
            personas=3,
            notificaciones=True,
            alerta_fuga=True,
            costo_por_litro=DEFAULT_COSTO_POR_LITRO,
        )

    return ConfiguracionResponse(
        limite_diario=row[0],
        personas=row[1],
        notificaciones=row[2],
        alerta_fuga=row[3],
        costo_por_litro=row[4] if row[4] is not None else DEFAULT_COSTO_POR_LITRO,
    )

@router.post("/configuracion")
def guardar_configuracion(data: ConfiguracionUpdate, authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    costo = data.costo_por_litro if data.costo_por_litro is not None else DEFAULT_COSTO_POR_LITRO

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO configuraciones (
                usuario_id, limite_diario, personas, notificaciones, alerta_fuga, costo_por_litro
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (usuario_id)
            DO UPDATE SET
                limite_diario = EXCLUDED.limite_diario,
                personas = EXCLUDED.personas,
                notificaciones = EXCLUDED.notificaciones,
                alerta_fuga = EXCLUDED.alerta_fuga,
                costo_por_litro = EXCLUDED.costo_por_litro,
                updated_at = NOW()
            """,
            (
                usuario_id,
                data.limite_diario,
                data.personas,
                data.notificaciones,
                data.alerta_fuga,
                costo,
            ),
        )
        conn.commit()
        cur.close()

    return {
        "success": True,
        "config": {
            "limite_diario": data.limite_diario,
            "personas": data.personas,
            "notificaciones": data.notificaciones,
            "alerta_fuga": data.alerta_fuga,
            "costo_por_litro": costo,
        },
    }

@router.get("/historial")
def historial(page: int = 1, limit: int = 15, authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    with get_db() as conn:
        cur = conn.cursor()
        offset = (page - 1) * limit
        cur.execute(
            "SELECT fecha, litros FROM consumos WHERE usuario_id = %s ORDER BY fecha DESC LIMIT %s OFFSET %s",
            (usuario_id, limit, offset),
        )
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM consumos WHERE usuario_id = %s", (usuario_id,))
        total = cur.fetchone()[0]
        cur.execute(
            """
            SELECT limite_diario, costo_por_litro
            FROM configuraciones WHERE usuario_id = %s
            """,
            (usuario_id,),
        )
        cfg = cur.fetchone()
        limite = cfg[0] if cfg else 200
        costo_por_litro = (
            cfg[1] if cfg and cfg[1] is not None else DEFAULT_COSTO_POR_LITRO
        )
        items = [
            {
                "id": idx + 1 + offset,
                "fecha": str(r[0]),
                "litros": round(to_float(r[1]), 2),
                "limite": to_float(limite),
                "costo": round(to_float(r[1]) * to_float(costo_por_litro), 2),
                "estado": "excedido" if to_float(r[1]) > to_float(limite) else "normal",
                "ahorro": round(max(0, to_float(limite) - to_float(r[1])), 2),
            }
            for idx, r in enumerate(rows)
        ]
        cur.close()
        return {
            "items": items,
            "total": int(total or 0),
            "costo_por_litro": to_float(costo_por_litro, DEFAULT_COSTO_POR_LITRO),
        }
