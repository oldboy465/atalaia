import sqlite3
from typing import Any
from app.config import Config

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(Config.DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db() -> None:
    conn = get_db()
    cursor = conn.cursor()
    
    # Tabela: locais
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS locais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            descricao TEXT,
            latitude REAL,
            longitude REAL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Tabela: coletas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coletas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            local_id INTEGER NOT NULL,
            uptime_sec INTEGER NOT NULL,
            session_id INTEGER NOT NULL DEFAULT 1,
            temperatura REAL NOT NULL,
            umidade REAL NOT NULL,
            temperatura_kelvin REAL NOT NULL,
            pressao_vapor_sat REAL NOT NULL,
            pressao_vapor_real REAL NOT NULL,
            ponto_orvalho REAL NOT NULL,
            umidade_absoluta REAL NOT NULL,
            indice_calor REAL NOT NULL,
            mq135_raw INTEGER NOT NULL DEFAULT 0,
            ppm_co2 REAL NOT NULL DEFAULT 0.0,
            iaq_indice REAL NOT NULL DEFAULT 0.0,
            coletado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE ON UPDATE CASCADE
        );
    """)

    # Migrações defensivas estruturais caso a base SQLite já contenha dados prévios
    cursor.execute("PRAGMA table_info(coletas);")
    existing_cols = [row["name"] for row in cursor.fetchall()]

    if "session_id" not in existing_cols:
        cursor.execute("ALTER TABLE coletas ADD COLUMN session_id INTEGER DEFAULT 1;")
    if "mq135_raw" not in existing_cols:
        cursor.execute("ALTER TABLE coletas ADD COLUMN mq135_raw INTEGER DEFAULT 0;")
    if "ppm_co2" not in existing_cols:
        cursor.execute("ALTER TABLE coletas ADD COLUMN ppm_co2 REAL DEFAULT 0.0;")
    if "iaq_indice" not in existing_cols:
        cursor.execute("ALTER TABLE coletas ADD COLUMN iaq_indice REAL DEFAULT 0.0;")

    # Índices para alta performance analítica e agregativa
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coletas_local_data ON coletas(local_id, coletado_em);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coletas_metricas ON coletas(temperatura, umidade);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coletas_session ON coletas(session_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coletas_gases ON coletas(mq135_raw, ppm_co2, iaq_indice);")

    conn.commit()
    conn.close()
    print(f"[DATABASE] SQLite inicializado com sucesso em: {Config.DB_PATH}")