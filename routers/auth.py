# ============================================================
# routers/auth.py – Registro, login, verificación y reset
# ============================================================
from fastapi import APIRouter, HTTPException
import bcrypt
from jose import jwt
from datetime import datetime, timedelta
import os
from database import get_connection
from schemas import UsuarioCreate, LoginRequest, VerificarCodigo, RecuperarPassword, ResetPassword
from routers.notificaciones import generar_codigo, enviar_codigo_verificacion, enviar_codigo_reset

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY     = os.getenv("SECRET_KEY", "clave_secreta")
ALGORITHM      = os.getenv("ALGORITHM", "HS256")
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
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
    except Exception as e:
        print(f"Error verificando token: {e}")
        raise HTTPException(status_code=401, detail="Token inválido")

@router.post("/register")
def register(data: UsuarioCreate):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        hashed = hash_password(data.contrasena)
        codigo = generar_codigo()
        expira = datetime.utcnow() + timedelta(minutes=10)

        cur.execute("""
            INSERT INTO usuarios (nombre, email, usuario, contrasena, telefono, verificado, codigo_verificacion, codigo_expira)
            VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s)
            RETURNING id, nombre, email, usuario
        """, (data.nombre, data.email, data.usuario, hashed, data.telefono, codigo, expira))

        user = cur.fetchone()
        cur.execute("INSERT INTO configuraciones (usuario_id) VALUES (%s)", (user[0],))
        conn.commit()

        enviar_codigo_verificacion(data.email, codigo)

        return {
            "mensaje": "Registro exitoso. Revisa tu email para verificar tu cuenta.",
            "email": data.email,
            "requiere_verificacion": True
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.post("/verificar")
def verificar(data: VerificarCodigo):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT id, nombre, email, usuario, codigo_verificacion, codigo_expira FROM usuarios WHERE email = %s",
        (data.email,)
    )
    user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user[4] != data.codigo:
        raise HTTPException(status_code=400, detail="Código incorrecto")

    if datetime.utcnow() > user[5]:
        raise HTTPException(status_code=400, detail="Código expirado, solicita uno nuevo")

    cur.execute("UPDATE usuarios SET verificado = TRUE, codigo_verificacion = NULL WHERE id = %s", (user[0],))
    conn.commit()
    cur.close()
    conn.close()

    token = crear_token({"sub": str(user[0]), "usuario": user[3]})
    return {
        "token": token,
        "user": {"id": user[0], "nombre": user[1], "email": user[2]}
    }

@router.post("/reenviar-codigo")
def reenviar_codigo(data: RecuperarPassword):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT id, email FROM usuarios WHERE email = %s", (data.email,))
    user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Email no encontrado")

    codigo = generar_codigo()
    expira = datetime.utcnow() + timedelta(minutes=10)
    cur.execute(
        "UPDATE usuarios SET codigo_verificacion = %s, codigo_expira = %s WHERE id = %s",
        (codigo, expira, user[0])
    )
    conn.commit()
    cur.close()
    conn.close()

    enviar_codigo_verificacion(data.email, codigo)
    return {"mensaje": "Código reenviado a tu email"}

@router.post("/login")
def login(data: LoginRequest):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT id, nombre, email, usuario, contrasena, verificado FROM usuarios WHERE usuario = %s",
        (data.usuario,)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not verify_password(data.contrasena, user[4]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    if not user[5]:
        raise HTTPException(status_code=403, detail="Cuenta no verificada. Revisa tu email.")

    token = crear_token({"sub": str(user[0]), "usuario": user[3]})
    return {
        "token": token,
        "user": {"id": user[0], "nombre": user[1], "email": user[2]}
    }

@router.post("/recuperar-password")
def recuperar_password(data: RecuperarPassword):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT id, email FROM usuarios WHERE email = %s", (data.email,))
    user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Email no encontrado")

    codigo = generar_codigo()
    expira = datetime.utcnow() + timedelta(minutes=10)
    cur.execute(
        "UPDATE usuarios SET codigo_verificacion = %s, codigo_expira = %s WHERE id = %s",
        (codigo, expira, user[0])
    )
    conn.commit()
    cur.close()
    conn.close()

    enviar_codigo_reset(data.email, codigo)
    return {"mensaje": "Código enviado a tu email"}

@router.post("/reset-password")
def reset_password(data: ResetPassword):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT id, codigo_verificacion, codigo_expira FROM usuarios WHERE email = %s",
        (data.email,)
    )
    user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user[1] != data.codigo:
        raise HTTPException(status_code=400, detail="Código incorrecto")

    if datetime.utcnow() > user[2]:
        raise HTTPException(status_code=400, detail="Código expirado")

    hashed = hash_password(data.nueva_contrasena)
    cur.execute(
        "UPDATE usuarios SET contrasena = %s, codigo_verificacion = NULL WHERE id = %s",
        (hashed, user[0])
    )
    conn.commit()
    cur.close()
    conn.close()

    return {"mensaje": "Contraseña actualizada correctamente ✅"}

@router.post("/token-sensor")
def token_sensor(data: LoginRequest):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT id, nombre, email, usuario, contrasena FROM usuarios WHERE usuario = %s",
        (data.usuario,)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not verify_password(data.contrasena, user[4]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    payload = {"sub": str(user[0]), "usuario": user[3], "tipo": "sensor"}
    token   = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token, "mensaje": "Token permanente para ESP32 generado ✅"}