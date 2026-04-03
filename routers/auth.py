# ============================================================
# routers/auth.py – Registro y login de usuarios
# ============================================================
from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import os

# IMPORTS IMPORTANTES (así déjalos)
from database import get_connection
from schemas import UsuarioCreate, LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "clave_secreta")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))


def crear_token(data: dict):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verificar_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")


@router.post("/register")
def register(data: UsuarioCreate):
    conn = get_connection()
    cur = conn.cursor()
    try:
        hashed = pwd_context.hash(data.contrasena)

        cur.execute(
            "INSERT INTO usuarios (nombre, email, usuario, contrasena) VALUES (%s, %s, %s, %s) RETURNING id, nombre, email, usuario",
            (data.nombre, data.email, data.usuario, hashed)
        )
        user = cur.fetchone()

        # Crear configuración por defecto
        cur.execute(
            "INSERT INTO configuraciones (usuario_id) VALUES (%s)",
            (user[0],)
        )

        conn.commit()

        token = crear_token({"sub": str(user[0]), "usuario": user[3]})

        return {
            "token": token,
            "user": {
                "id": user[0],
                "nombre": user[1],
                "email": user[2]
            }
        }

    except Exception:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Usuario o email ya existe")

    finally:
        cur.close()
        conn.close()


@router.post("/login")
def login(data: LoginRequest):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, nombre, email, usuario, contrasena FROM usuarios WHERE usuario = %s",
        (data.usuario,)
    )
    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user or not pwd_context.verify(data.contrasena, user[4]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = crear_token({"sub": str(user[0]), "usuario": user[3]})

    return {
        "token": token,
        "user": {
            "id": user[0],
            "nombre": user[1],
            "email": user[2]
        }
    }