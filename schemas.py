# ============================================================
# schemas.py – Modelos de datos (Pydantic)
# ============================================================
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date

class UsuarioCreate(BaseModel):
    nombre: str
    email: EmailStr
    usuario: str
    contrasena: str
    telefono: Optional[str] = None

class LoginRequest(BaseModel):
    usuario: str
    contrasena: str

class Token(BaseModel):
    token: str
    user: dict

class VerificarCodigo(BaseModel):
    email: str
    codigo: str

class RecuperarPassword(BaseModel):
    email: str

class ResetPassword(BaseModel):
    email: str
    codigo: str
    nueva_contrasena: str

class ConsumoHoy(BaseModel):
    fecha: str
    litros: float
    limite: float
    personas: int
    costo_por_litro: float
    costo_estimado: float
    flujo_actual: float
    temperatura_agua: float
    sensor: dict

class ConsumoSemanal(BaseModel):
    dia: str
    litros: float
    limite: float

class ConsumoMensual(BaseModel):
    fecha: str
    litros: float
    limite: float

class ConfiguracionUpdate(BaseModel):
    limite_diario: Optional[float] = 200
    personas: Optional[int] = 3
    notificaciones: Optional[bool] = True
    alerta_fuga: Optional[bool] = True
    costo_por_litro: Optional[float] = Field(default=0.005, ge=0, le=0.05)

class ConfiguracionResponse(BaseModel):
    limite_diario: float
    personas: int
    notificaciones: bool
    alerta_fuga: bool
    costo_por_litro: float

class SensorData(BaseModel):
    litros: float
    flujo_actual: Optional[float] = 0
    temperatura_agua: Optional[float] = 18
    sensor_id: Optional[str] = "ESP32-001"