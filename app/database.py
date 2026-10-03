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
            temperatura REAL NOT NULL,
            umidade REAL NOT NULL,
            temperatura_kelvin REAL NOT NULL,
            pressao_vapor_sat REAL NOT NULL,
            pressao_vapor_real REAL NOT NULL,
            ponto_orvalho REAL NOT NULL,
            umidade_absoluta REAL NOT NULL,
            indice_calor REAL NOT NULL,
            coletado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE ON UPDATE CASCADE
        );
    """)

    # Índices para alta performance analítica
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coletas_local_data ON coletas(local_id, coletado_em);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coletas_metricas ON coletas(temperatura, umidade);")

    conn.commit()
    conn.close()
    print(f"[DATABASE] SQLite inicializado com sucesso em: {Config.DB_PATH}")