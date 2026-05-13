# ============================================================
# routers/auth.py – Registro, login, verificación y reset
# ============================================================
from fastapi import APIRouter, HTTPException
import bcrypt
from jose import jwt
from datetime import datetime, timedelta
import os
from database import get_db, limpiar_pendientes_expirados
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
    limpiar_pendientes_expirados()
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id FROM usuarios WHERE email = %s OR usuario = %s",
                (data.email, data.usuario)
            )
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Usuario o email ya existe")

            codigo = generar_codigo()
            expira = datetime.utcnow() + timedelta(minutes=10)

            enviar_codigo_verificacion(data.email, codigo)

            cur.execute("""
                INSERT INTO registros_pendientes 
                (nombre, email, usuario, contrasena, telefono, codigo, expira)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET
                    codigo = EXCLUDED.codigo,
                    expira = EXCLUDED.expira
            """, (data.nombre, data.email, data.usuario,
                  hash_password(data.contrasena), data.telefono, codigo, expira))
            conn.commit()

            return {
                "mensaje": "Revisa tu email para verificar tu cuenta.",
                "email": data.email,
                "requiere_verificacion": True
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()

@router.post("/verificar")
def verificar(data: VerificarCodigo):
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT nombre, email, usuario, contrasena, telefono, codigo, expira FROM registros_pendientes WHERE email = %s",
                (data.email,)
            )
            pendiente = cur.fetchone()

            if not pendiente:
                raise HTTPException(status_code=404, detail="Solicitud no encontrada o ya verificada")
            if pendiente[5] != data.codigo:
                raise HTTPException(status_code=400, detail="Código incorrecto")
            if datetime.utcnow() > pendiente[6]:
                raise HTTPException(status_code=400, detail="Código expirado, solicita uno nuevo")

            cur.execute("""
                INSERT INTO usuarios (nombre, email, usuario, contrasena, telefono, verificado)
                VALUES (%s, %s, %s, %s, %s, TRUE)
                RETURNING id, nombre, email, usuario
            """, (pendiente[0], pendiente[1], pendiente[2], pendiente[3], pendiente[4]))
            user = cur.fetchone()

            cur.execute("INSERT INTO configuraciones (usuario_id) VALUES (%s)", (user[0],))
            cur.execute("DELETE FROM registros_pendientes WHERE email = %s", (data.email,))

            conn.commit()

            token = crear_token({"sub": str(user[0]), "usuario": user[3]})
            return {"token": token, "user": {"id": user[0], "nombre": user[1], "email": user[2]}}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            cur.close()

@router.post("/reenviar-codigo")
def reenviar_codigo(data: RecuperarPassword):
    with get_db() as conn:
        cur = conn.cursor()
        try:
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
            enviar_codigo_verificacion(data.email, codigo)
            return {"mensaje": "Código reenviado a tu email"}
        finally:
            cur.close()

@router.post("/login")
def login(data: LoginRequest):
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, nombre, email, usuario, contrasena, verificado FROM usuarios WHERE usuario = %s",
                (data.usuario,)
            )
            user = cur.fetchone()
            if not user or not verify_password(data.contrasena, user[4]):
                raise HTTPException(status_code=401, detail="Credenciales incorrectas")
            if not user[5]:
                raise HTTPException(status_code=403, detail="Cuenta no verificada. Revisa tu email.")
            token = crear_token({"sub": str(user[0]), "usuario": user[3]})
            return {"token": token, "user": {"id": user[0], "nombre": user[1], "email": user[2]}}
        finally:
            cur.close()

@router.post("/recuperar-password")
def recuperar_password(data: RecuperarPassword):
    with get_db() as conn:
        cur = conn.cursor()
        try:
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
            enviar_codigo_reset(data.email, codigo)
            return {"mensaje": "Código enviado a tu email"}
        finally:
            cur.close()

@router.post("/reset-password")
def reset_password(data: ResetPassword):
    with get_db() as conn:
        cur = conn.cursor()
        try:
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
            return {"mensaje": "Contraseña actualizada correctamente ✅"}
        finally:
            cur.close()

@router.post("/token-sensor")
def token_sensor(data: LoginRequest):
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, nombre, email, usuario, contrasena FROM usuarios WHERE usuario = %s",
                (data.usuario,)
            )
            user = cur.fetchone()
            if not user or not verify_password(data.contrasena, user[4]):
                raise HTTPException(status_code=401, detail="Credenciales incorrectas")
            payload = {"sub": str(user[0]), "usuario": user[3], "tipo": "sensor"}
            token   = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
            return {"token": token, "mensaje": "Token permanente para ESP32 generado ✅"}
        finally:
            cur.close()
