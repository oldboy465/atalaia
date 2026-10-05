from typing import Any, Dict, List, Optional
import sqlite3
from app.database import get_db

class DataModel:
    @staticmethod
    def ensure_schema_migrations() -> None:
        """
        Garante defensivamente que as colunas essenciais adicionadas
        (session_id, latitude, longitude) existam no banco SQLite.
        """
        conn = get_db()
        cursor = conn.cursor()
        try:
            # Verifica colunas da tabela coletas
            cursor.execute("PRAGMA table_info(coletas);")
            coletas_cols = [row["name"] for row in cursor.fetchall()]
            if "session_id" not in coletas_cols:
                cursor.execute("ALTER TABLE coletas ADD COLUMN session_id INTEGER DEFAULT 1;")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_coletas_session ON coletas(session_id);")

            # Verifica colunas da tabela locais
            cursor.execute("PRAGMA table_info(locais);")
            locais_cols = [row["name"] for row in cursor.fetchall()]
            if "latitude" not in locais_cols:
                cursor.execute("ALTER TABLE locais ADD COLUMN latitude REAL;")
            if "longitude" not in locais_cols:
                cursor.execute("ALTER TABLE locais ADD COLUMN longitude REAL;")

            conn.commit()
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()

    @staticmethod
    def cleanup_orphaned_locais() -> int:
        """
        Exclui da tabela locais qualquer ponto cadastrado que não
        possua nenhuma coleta vinculada no banco de dados.
        """
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                DELETE FROM locais 
                WHERE id NOT IN (SELECT DISTINCT local_id FROM coletas)
            """)
            conn.commit()
            return cursor.rowcount if cursor.rowcount is not None else 0
        finally:
            conn.close()

    @staticmethod
    def get_or_create_local(
        nome: str, 
        descricao: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> int:
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, descricao, latitude, longitude FROM locais WHERE nome = ?", (nome,))
            row = cursor.fetchone()
            if row:
                local_id = int(row["id"])
                updates = []
                params: List[Any] = []

                if descricao is not None and str(descricao).strip() != "":
                    updates.append("descricao = ?")
                    params.append(descricao)
                if latitude is not None:
                    updates.append("latitude = ?")
                    params.append(latitude)
                if longitude is not None:
                    updates.append("longitude = ?")
                    params.append(longitude)

                if updates:
                    updates.append("atualizado_em = CURRENT_TIMESTAMP")
                    params.append(local_id)
                    query = f"UPDATE locais SET {', '.join(updates)} WHERE id = ?"
                    cursor.execute(query, tuple(params))
                    conn.commit()

                return local_id

            cursor.execute(
                "INSERT INTO locais (nome, descricao, latitude, longitude) VALUES (?, ?, ?, ?)",
                (nome, descricao, latitude, longitude)
            )
            conn.commit()
            last_id = cursor.lastrowid
            if last_id is None:
                raise RuntimeError("Falha ao capturar o ID gerado para o novo local.")
            return int(last_id)
        finally:
            conn.close()

    @staticmethod
    def list_locais(only_with_data: bool = False) -> List[Dict[str, Any]]:
        """
        Lista os locais cadastrados. Quando only_with_data=True, traz apenas
        os locais que possuem coletas registradas.
        """
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        try:
            if only_with_data:
                query = """
                    SELECT DISTINCT l.* 
                    FROM locais l
                    INNER JOIN coletas c ON l.id = c.local_id
                    ORDER BY l.nome ASC
                """
            else:
                query = "SELECT * FROM locais ORDER BY nome ASC"

            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def list_locais_geo() -> List[Dict[str, Any]]:
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        try:
            query = """
                SELECT 
                    l.id, l.nome, l.descricao, l.latitude, l.longitude,
                    COUNT(c.id) as total_coletas,
                    ROUND(AVG(c.temperatura), 2) as media_temp,
                    ROUND(AVG(c.umidade), 2) as media_umid,
                    ROUND(AVG(c.indice_calor), 2) as media_sensacao,
                    ROUND(AVG(c.ponto_orvalho), 2) as media_orvalho,
                    ROUND(AVG(c.umidade_absoluta), 2) as media_absoluta,
                    ROUND(AVG(c.pressao_vapor_real), 2) as media_pressao,
                    MAX(c.coletado_em) as ultima_coleta,
                    MIN(c.coletado_em) as primeira_coleta
                FROM locais l
                INNER JOIN coletas c ON l.id = c.local_id
                GROUP BY l.id
                HAVING COUNT(c.id) > 0
                ORDER BY l.nome ASC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def update_local(
        local_id: int, 
        nome: str, 
        descricao: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> None:
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """UPDATE locais 
                   SET nome = ?, descricao = ?, latitude = ?, longitude = ?, atualizado_em = CURRENT_TIMESTAMP 
                   WHERE id = ?""",
                (nome, descricao, latitude, longitude, local_id)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def insert_batch_coletas(local_id: int, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        query = """
            INSERT INTO coletas (
                local_id, uptime_sec, session_id, temperatura, umidade,
                temperatura_kelvin, pressao_vapor_sat, pressao_vapor_real,
                ponto_orvalho, umidade_absoluta, indice_calor, coletado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        data = [
            (
                local_id, 
                int(r['uptime_sec']), 
                int(r.get('session_id', r.get('s', 1))),
                float(r['temperatura']), 
                float(r['umidade']),
                float(r['temperatura_kelvin']), 
                float(r['pressao_vapor_sat']), 
                float(r['pressao_vapor_real']),
                float(r['ponto_orvalho']), 
                float(r['umidade_absoluta']), 
                float(r['indice_calor']), 
                str(r['coletado_em'])
            )
            for r in records
        ]
        try:
            cursor.executemany(query, data)
            conn.commit()
            rowcount = cursor.rowcount
            return int(rowcount) if rowcount is not None and rowcount >= 0 else 0
        finally:
            conn.close()

    @staticmethod
    def list_coletas(
        local_id: Optional[int] = None, 
        limit: int = 1000,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retorna as amostras para os gráficos com garantia de trazer
        os dados cronológicos corretos e sem truncar o histórico do local.
        """
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        try:
            query = """
                SELECT c.*, l.nome as local_nome 
                FROM coletas c 
                JOIN locais l ON c.local_id = l.id 
                WHERE 1=1
            """
            params: List[Any] = []
            if local_id is not None:
                query += " AND c.local_id = ?"
                params.append(local_id)
            if data_inicio:
                query += " AND c.coletado_em >= ?"
                params.append(f"{data_inicio} 00:00:00")
            if data_fim:
                query += " AND c.coletado_em <= ?"
                params.append(f"{data_fim} 23:59:59")
            
            query += " ORDER BY c.coletado_em DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def get_local_metrics_summary(
        local_id: Optional[int] = None,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calcula o resumo agregado completo diretamente no motor SQL,
        evitando que amostragens parciais provoquem números estáticos nos cards.
        """
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        try:
            where_clauses = ["1=1"]
            params: List[Any] = []

            if local_id is not None:
                where_clauses.append("c.local_id = ?")
                params.append(local_id)
            if data_inicio:
                where_clauses.append("c.coletado_em >= ?")
                params.append(f"{data_inicio} 00:00:00")
            if data_fim:
                where_clauses.append("c.coletado_em <= ?")
                params.append(f"{data_fim} 23:59:59")

            where_str = " AND ".join(where_clauses)

            query = f"""
                SELECT 
                    COUNT(c.id) as total_amostras,
                    ROUND(AVG(c.temperatura), 2) as avg_temp,
                    ROUND(AVG(c.umidade), 2) as avg_hum,
                    ROUND(AVG(c.indice_calor), 2) as avg_hi,
                    ROUND(AVG(c.ponto_orvalho), 2) as avg_dp,
                    ROUND(AVG(c.umidade_absoluta), 2) as avg_ah,
                    ROUND(AVG(c.pressao_vapor_real), 2) as avg_ea,
                    MAX(c.temperatura) as max_temp,
                    MIN(c.temperatura) as min_temp,
                    MAX(c.umidade) as max_hum,
                    MIN(c.umidade) as min_hum,
                    MAX(c.coletado_em) as last_collected
                FROM coletas c
                JOIN locais l ON c.local_id = l.id
                WHERE {where_str}
            """
            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            
            # Última leitura pontual instantânea
            last_query = f"""
                SELECT c.*, l.nome as local_nome
                FROM coletas c
                JOIN locais l ON c.local_id = l.id
                WHERE {where_str}
                ORDER BY c.coletado_em DESC LIMIT 1
            """
            cursor.execute(last_query, tuple(params))
            last_row = cursor.fetchone()

            return {
                "aggregates": dict(row) if row else {},
                "latest": dict(last_row) if last_row else None
            }
        finally:
            conn.close()

    @staticmethod
    def list_coletas_paginadas(
        local_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 20,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        try:
            where_clauses = ["1=1"]
            params: List[Any] = []

            if local_id is not None:
                where_clauses.append("c.local_id = ?")
                params.append(local_id)
            if data_inicio:
                where_clauses.append("c.coletado_em >= ?")
                params.append(f"{data_inicio} 00:00:00")
            if data_fim:
                where_clauses.append("c.coletado_em <= ?")
                params.append(f"{data_fim} 23:59:59")
            if search:
                where_clauses.append("(l.nome LIKE ? OR c.coletado_em LIKE ? OR CAST(c.id AS TEXT) LIKE ?)")
                params.append(f"%{search}%")
                params.append(f"%{search}%")
                params.append(f"%{search}%")

            where_str = " AND ".join(where_clauses)

            # Contagem total e estatísticas rápidas
            agg_query = f"""
                SELECT 
                    COUNT(c.id) as total,
                    ROUND(AVG(c.temperatura), 2) as avg_temp,
                    ROUND(AVG(c.umidade), 2) as avg_hum,
                    MAX(c.temperatura) as max_temp,
                    MIN(c.temperatura) as min_temp
                FROM coletas c
                JOIN locais l ON c.local_id = l.id
                WHERE {where_str}
            """
            cursor.execute(agg_query, tuple(params))
            agg_row = cursor.fetchone()
            total_records = int(agg_row["total"]) if agg_row and agg_row["total"] is not None else 0

            page = max(1, page)
            per_page = max(1, per_page)
            offset = (page - 1) * per_page
            
            data_query = f"""
                SELECT c.*, l.nome as local_nome 
                FROM coletas c 
                JOIN locais l ON c.local_id = l.id 
                WHERE {where_str}
                ORDER BY c.coletado_em DESC 
                LIMIT ? OFFSET ?
            """
            data_params = params + [per_page, offset]
            cursor.execute(data_query, tuple(data_params))
            rows = cursor.fetchall()

            total_pages = max(1, (total_records + per_page - 1) // per_page)

            return {
                "records": [dict(r) for r in rows],
                "total": total_records,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "stats": {
                    "avg_temp": agg_row["avg_temp"] if agg_row and agg_row["avg_temp"] is not None else 0,
                    "avg_hum": agg_row["avg_hum"] if agg_row and agg_row["avg_hum"] is not None else 0,
                    "max_temp": agg_row["max_temp"] if agg_row and agg_row["max_temp"] is not None else 0,
                    "min_temp": agg_row["min_temp"] if agg_row and agg_row["min_temp"] is not None else 0
                }
            }
        finally:
            conn.close()

    @staticmethod
    def update_coleta_datestamp(coleta_id: int, novo_timestamp: str) -> None:
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE coletas SET coletado_em = ? WHERE id = ?",
                (novo_timestamp, coleta_id)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def delete_coleta(coleta_id: int) -> None:
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM coletas WHERE id = ?", (coleta_id,))
            conn.commit()
        finally:
            conn.close()
        # Remove o local automaticamente se esta era sua última coleta
        DataModel.cleanup_orphaned_locais()

    @staticmethod
    def delete_coletas_batch(coleta_ids: List[int]) -> int:
        if not coleta_ids:
            return 0
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        try:
            placeholders = ",".join(["?"] * len(coleta_ids))
            query = f"DELETE FROM coletas WHERE id IN ({placeholders})"
            cursor.execute(query, tuple(coleta_ids))
            conn.commit()
            deleted = cursor.rowcount if cursor.rowcount is not None else 0
        finally:
            conn.close()
        # Faxina em lote de quaisquer locais que tenham ficado sem coletas
        DataModel.cleanup_orphaned_locais()
        return deleted

    @staticmethod
    def clear_local_coletas(local_id: int) -> int:
        """
        Exclui todas as coletas vinculadas a um determinado local
        e remove o cadastro do local correspondente.
        """
        DataModel.ensure_schema_migrations()
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM coletas WHERE local_id = ?", (local_id,))
            cursor.execute("DELETE FROM locais WHERE id = ?", (local_id,))
            conn.commit()
            return cursor.rowcount if cursor.rowcount is not None else 0
        finally:
            conn.close()