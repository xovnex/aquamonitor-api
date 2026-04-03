# ============================================================
# routers/configuracion.py – Configuración del usuario
# ============================================================
from fastapi import APIRouter, Header
from database import get_connection
from routers.auth import verificar_token
from schemas import ConfiguracionUpdate

router = APIRouter(tags=["configuracion"])

def get_user_id(authorization: str):
    token = authorization.split(" ")[1]
    payload = verificar_token(token)
    return int(payload["sub"])

@router.get("/historial")
def historial(page: int = 1, limit: int = 15, authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    conn = get_connection()
    cur = conn.cursor()

    offset = (page - 1) * limit
    cur.execute(
        "SELECT fecha, litros FROM consumos WHERE usuario_id = %s ORDER BY fecha DESC LIMIT %s OFFSET %s",
        (usuario_id, limit, offset)
    )
    rows = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM consumos WHERE usuario_id = %s", (usuario_id,))
    total = cur.fetchone()[0]

    cur.execute(
        "SELECT limite_diario FROM configuraciones WHERE usuario_id = %s",
        (usuario_id,)
    )
    cfg = cur.fetchone()
    limite = cfg[0] if cfg else 200

    cur.close()
    conn.close()

    items = [
        {
            "id": idx + 1 + offset,
            "fecha": str(r[0]),
            "litros": r[1],
            "limite": limite,
            "estado": "excedido" if r[1] > limite else "normal",
            "ahorro": max(0, limite - r[1])
        }
        for idx, r in enumerate(rows)
    ]
    return {"items": items, "total": total}

@router.post("/configuracion")
def guardar_configuracion(data: ConfiguracionUpdate, authorization: str = Header(None)):
    usuario_id = get_user_id(authorization)
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO configuraciones (usuario_id, limite_diario, personas, notificaciones, alerta_fuga)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (usuario_id)
        DO UPDATE SET
            limite_diario = EXCLUDED.limite_diario,
            personas = EXCLUDED.personas,
            notificaciones = EXCLUDED.notificaciones,
            alerta_fuga = EXCLUDED.alerta_fuga,
            updated_at = NOW()
    """, (usuario_id, data.limite_diario, data.personas, data.notificaciones, data.alerta_fuga))

    conn.commit()
    cur.close()
    conn.close()
    return {"success": True, "config": data}