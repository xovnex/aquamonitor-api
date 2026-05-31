# ============================================================
# main.py – Punto de entrada de la API FastAPI
# ============================================================
import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db, limpiar_pendientes_expirados
from routers import auth, consumo, configuracion, analisis


async def ping_propio():
    """Mantiene la API despierta en Render. No envía datos del ESP32."""
    while True:
        await asyncio.sleep(14 * 60)
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://aquamonitor-api-1.onrender.com/ping")
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    limpiar_pendientes_expirados()  # limpia basura de arranques anteriores
    asyncio.create_task(ping_propio())
    yield


app = FastAPI(title="AquaMonitor API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(consumo.router)
app.include_router(configuracion.router)
app.include_router(analisis.router)


@app.get("/")
def root():
    return {"message": "AquaMonitor API funcionando ✅"}


@app.get("/ping")
def ping():
    return {"status": "ok"}