"""
Módulo de Persistência SQLite - Projeto Estação Ambiental Atalaia
Suporte a local físico, índices multivariados, exclusão seletiva e integridade transacional.
"""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'atalaia.db')

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Tabela unificada contendo o local de coleta
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                esp_seq INTEGER UNIQUE NOT NULL,
                timestamp TEXT NOT NULL,
                local TEXT NOT NULL DEFAULT 'Geral',
                temperatura REAL NOT NULL,
                umidade REAL NOT NULL,
                ponto_orvalho REAL NOT NULL,
                sensacao_termica REAL NOT NULL,
                pressao_vapor REAL NOT NULL DEFAULT 0.0,
                umidade_absoluta REAL NOT NULL DEFAULT 0.0,
                entalpia REAL NOT NULL DEFAULT 0.0,
                indice_thom REAL NOT NULL DEFAULT 0.0,
                intervalo_segundos REAL NOT NULL,
                origem TEXT NOT NULL,
                sincronizado_em TEXT NOT NULL
            )
        ''')
        
        # Migração defensiva: adiciona coluna local caso banco antigo exista
        cursor.execute("PRAGMA table_info(registros)")
        colunas = [col[1] for col in cursor.fetchall()]
        if 'local' not in colunas:
            cursor.execute("ALTER TABLE registros ADD COLUMN local TEXT NOT NULL DEFAULT 'Geral'")
        if 'pressao_vapor' not in colunas:
            cursor.execute("ALTER TABLE registros ADD COLUMN pressao_vapor REAL NOT NULL DEFAULT 0.0")
        if 'umidade_absoluta' not in colunas:
            cursor.execute("ALTER TABLE registros ADD COLUMN umidade_absoluta REAL NOT NULL DEFAULT 0.0")
        if 'entalpia' not in colunas:
            cursor.execute("ALTER TABLE registros ADD COLUMN entalpia REAL NOT NULL DEFAULT 0.0")
        if 'indice_thom' not in colunas:
            cursor.execute("ALTER TABLE registros ADD COLUMN indice_thom REAL NOT NULL DEFAULT 0.0")

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON registros(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_local ON registros(local)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_esp_seq ON registros(esp_seq)')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                executado_em TEXT NOT NULL,
                local TEXT NOT NULL,
                registros_baixados INTEGER NOT NULL,
                status TEXT NOT NULL,
                mensagem TEXT
            )
        ''')
        
        conn.commit()

def insert_batch_registros(records):
    """
    Insere lote de registros com identificação de local e novas métricas.
    """
    if not records:
        return 0

    query = '''
        INSERT OR IGNORE INTO registros (
            esp_seq, timestamp, local, temperatura, umidade, 
            ponto_orvalho, sensacao_termica, pressao_vapor, umidade_absoluta,
            entalpia, indice_thom, intervalo_segundos, origem, sincronizado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(query, records)
        linhas_inseridas = cursor.rowcount
        conn.commit()
        return linhas_inseridas

def log_sync_event(local, registros_baixados, status, mensagem=""):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sync_history (executado_em, local, registros_baixados, status, mensagem)
            VALUES (datetime('now', 'localtime'), ?, ?, ?, ?)
        ''', (local, registros_baixados, status, mensagem))
        conn.commit()

def obter_locais_unicos():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT local FROM registros WHERE local IS NOT NULL AND local != '' ORDER BY local ASC")
        return [row[0] for row in cursor.fetchall()]

def excluir_registros(data_inicio=None, data_fim=None, hora_inicio=None, hora_fim=None, local=None):
    """
    Exclui registros com base nos critérios de data, hora e local.
    Se nenhum parâmetro for fornecido, executa limpeza completa (TRUNCATE).
    """
    query = "DELETE FROM registros WHERE 1=1"
    params = []

    if data_inicio:
        query += " AND date(timestamp) >= ?"
        params.append(data_inicio)
    if data_fim:
        query += " AND date(timestamp) <= ?"
        params.append(data_fim)
    if hora_inicio:
        query += " AND time(timestamp) >= ?"
        params.append(hora_inicio)
    if hora_fim:
        query += " AND time(timestamp) <= ?"
        params.append(hora_fim)
    if local and local != 'TODOS':
        query += " AND local = ?"
        params.append(local)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        deletados = cursor.rowcount
        conn.commit()
        
        # Se esvaziou a tabela, reseta auto-incremento
        cursor.execute("SELECT COUNT(*) FROM registros")
        restantes = cursor.fetchone()[0]
        if restantes == 0:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='registros'")
            conn.commit()
            
        return deletados