# ============================================================
# routers/auth.py – Registro y login de usuarios
# ============================================================
from fastapi import APIRouter, HTTPException
import bcrypt
from jose import jwt
from datetime import datetime, timedelta
import os
from database import get_connection
from schemas import UsuarioCreate, LoginRequest, Token

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "clave_secreta")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def crear_token(data: dict):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verificar_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except:
        raise HTTPException(status_code=401, detail="Token inválido")

@router.post("/register")
def register(data: UsuarioCreate):
    conn = get_connection()
    cur = conn.cursor()
    try:
        hashed = hash_password(data.contrasena)
        cur.execute(
            "INSERT INTO usuarios (nombre, email, usuario, contrasena) VALUES (%s, %s, %s, %s) RETURNING id, nombre, email, usuario",
            (data.nombre, data.email, data.usuario, hashed)
        )
        user = cur.fetchone()
        cur.execute(
            "INSERT INTO configuraciones (usuario_id) VALUES (%s)",
            (user[0],)
        )
        conn.commit()
        token = crear_token({"sub": str(user[0]), "usuario": user[3]})
        return {
            "token": token,
            "user": {"id": user[0], "nombre": user[1], "email": user[2]}
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
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

    if not user or not verify_password(data.contrasena, user[4]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = crear_token({"sub": str(user[0]), "usuario": user[3]})
    return {
        "token": token,
        "user": {"id": user[0], "nombre": user[1], "email": user[2]}
    }

@router.post("/token-sensor")
def token_sensor(data: LoginRequest):
    """Genera un token permanente para el ESP8266"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, nombre, email, usuario, contrasena FROM usuarios WHERE usuario = %s",
        (data.usuario,)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not verify_password(data.contrasena, user[4]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    # Token sin expiración para el sensor
    payload = {"sub": str(user[0]), "usuario": user[3], "tipo": "sensor"}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "token": token,
        "mensaje": "Token permanente para ESP8266 generado ✅"
    }