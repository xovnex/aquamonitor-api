# ============================================================
# database.py – Conexión a Neon PostgreSQL
# ============================================================
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Crea las tablas si no existen"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            usuario VARCHAR(50) UNIQUE NOT NULL,
            contrasena VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS consumos (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER REFERENCES usuarios(id),
            fecha DATE NOT NULL DEFAULT CURRENT_DATE,
            litros FLOAT NOT NULL DEFAULT 0,
            flujo_actual FLOAT DEFAULT 0,
            temperatura_agua FLOAT DEFAULT 18,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(usuario_id, fecha)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS configuraciones (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER REFERENCES usuarios(id) UNIQUE,
            limite_diario FLOAT DEFAULT 200,
            personas INTEGER DEFAULT 3,
            notificaciones BOOLEAN DEFAULT TRUE,
            alerta_fuga BOOLEAN DEFAULT TRUE,
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()
    conn.close()