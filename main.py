# ============================================================
# main.py – Punto de entrada de la API FastAPI
# ============================================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers import auth, consumo, configuracion

app = FastAPI(title="AquaMonitor API", version="1.0.0")

# CORS – permite peticiones desde cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crea tablas al iniciar
@app.on_event("startup")
def startup():
    init_db()

# Rutas
app.include_router(auth.router)
app.include_router(consumo.router)
app.include_router(configuracion.router)

@app.get("/")
def root():
    return {"message": "AquaMonitor API funcionando ✅"}