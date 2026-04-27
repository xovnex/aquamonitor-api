# ============================================================
# main.py – Punto de entrada de la API FastAPI
# ============================================================
import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers import auth, consumo, configuracion, analisis


async def ping_propio():
    while True:
        await asyncio.sleep(14 * 60)  # cada 14 minutos
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://aquamonitor-api-1.onrender.com/ping")
        except:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    asyncio.create_task(ping_propio())
    yield


app = FastAPI(title="AquaMonitor API", version="1.0.0", lifespan=lifespan)

# CORS – permite peticiones desde cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas
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