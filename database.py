# ============================================================
# database.py – Conexión a Neon PostgreSQL con connection pool
# ============================================================
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# ThreadedConnectionPool es thread-safe (SimpleConnectionPool no lo es)
connection_pool = pool.ThreadedConnectionPool(
    minconn=2,
    maxconn=15,
    dsn=DATABASE_URL
)

def get_connection():
    """Obtiene una conexión del pool"""
    return connection_pool.getconn()

def release_connection(conn):
    """Devuelve la conexión al pool"""
    connection_pool.putconn(conn)

@contextmanager
def get_db():
    """
    Context manager — libera la conexión automáticamente
    aunque haya excepción. Usar siempre así:

        with get_db() as conn:
            cur = conn.cursor()
            ...
    """
    conn = connection_pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        connection_pool.putconn(conn)

def init_db():
    """Crea las tablas si no existen"""
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                usuario VARCHAR(50) UNIQUE NOT NULL,
                contrasena VARCHAR(255) NOT NULL,
                telefono VARCHAR(20),
                verificado BOOLEAN DEFAULT FALSE,
                codigo_verificacion VARCHAR(6),
                codigo_expira TIMESTAMP,
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
                ultima_lectura TIMESTAMP DEFAULT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(usuario_id, fecha)
            );
        """)

        cur.execute("""
            ALTER TABLE consumos ADD COLUMN IF NOT EXISTS ultima_lectura TIMESTAMP DEFAULT NULL;
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS configuraciones (
                id SERIAL PRIMARY KEY,
                usuario_id INTEGER REFERENCES usuarios(id) UNIQUE,
                limite_diario FLOAT DEFAULT 200,
                personas INTEGER DEFAULT 3,
                notificaciones BOOLEAN DEFAULT TRUE,
                alerta_fuga BOOLEAN DEFAULT TRUE,
                costo_por_litro FLOAT DEFAULT 0.005,
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        cur.execute("""
            ALTER TABLE configuraciones
            ADD COLUMN IF NOT EXISTS costo_por_litro FLOAT DEFAULT 0.005;
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS registros_pendientes (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                usuario VARCHAR(50) NOT NULL,
                contrasena VARCHAR(255) NOT NULL,
                telefono VARCHAR(20),
                codigo VARCHAR(6),
                expira TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        conn.commit()
        cur.close()

def limpiar_pendientes_expirados():
    """Borra registros pendientes cuyo código ya expiró"""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM registros_pendientes WHERE expira < NOW();")
        conn.commit()
        cur.close()