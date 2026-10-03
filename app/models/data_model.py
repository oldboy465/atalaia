from typing import Any, Dict, List, Optional
from app.database import get_db

class DataModel:
    @staticmethod
    def get_or_create_local(
        nome: str, 
        descricao: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> int:
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM locais WHERE nome = ?", (nome,))
            row = cursor.fetchone()
            if row:
                local_id = int(row["id"])
                if latitude is not None and longitude is not None:
                    cursor.execute(
                        "UPDATE locais SET latitude = ?, longitude = ? WHERE id = ?",
                        (latitude, longitude, local_id)
                    )
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
    def list_locais() -> List[Dict[str, Any]]:
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM locais ORDER BY nome ASC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def list_locais_geo() -> List[Dict[str, Any]]:
        conn = get_db()
        cursor = conn.cursor()
        try:
            query = """
                SELECT 
                    l.id, l.nome, l.descricao, l.latitude, l.longitude,
                    COUNT(c.id) as total_coletas,
                    ROUND(AVG(c.temperatura), 1) as media_temp,
                    ROUND(AVG(c.umidade), 1) as media_umid,
                    ROUND(AVG(c.indice_calor), 1) as media_sensacao,
                    MAX(c.coletado_em) as ultima_coleta
                FROM locais l
                LEFT JOIN coletas c ON l.id = c.local_id
                GROUP BY l.id
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
        conn = get_db()
        cursor = conn.cursor()
        query = """
            INSERT INTO coletas (
                local_id, uptime_sec, temperatura, umidade,
                temperatura_kelvin, pressao_vapor_sat, pressao_vapor_real,
                ponto_orvalho, umidade_absoluta, indice_calor, coletado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        data = [
            (
                local_id, r['uptime_sec'], r['temperatura'], r['umidade'],
                r['temperatura_kelvin'], r['pressao_vapor_sat'], r['pressao_vapor_real'],
                r['ponto_orvalho'], r['umidade_absoluta'], r['indice_calor'], r['coletado_em']
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
        limit: int = 500,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        conn = get_db()
        cursor = conn.cursor()
        try:
            query = "SELECT c.*, l.nome as local_nome FROM coletas c JOIN locais l ON c.local_id = l.id WHERE 1=1"
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
    def list_coletas_paginadas(
        local_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 20,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
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
                where_clauses.append("(l.nome LIKE ? OR c.coletado_em LIKE ?)")
                params.append(f"%{search}%")
                params.append(f"%{search}%")

            where_str = " AND ".join(where_clauses)

            # Contagem total e agregações estatísticas
            agg_query = f"""
                SELECT 
                    COUNT(c.id) as total,
                    ROUND(AVG(c.temperatura), 1) as avg_temp,
                    ROUND(AVG(c.umidade), 1) as avg_hum,
                    MAX(c.temperatura) as max_temp,
                    MIN(c.temperatura) as min_temp
                FROM coletas c
                JOIN locais l ON c.local_id = l.id
                WHERE {where_str}
            """
            cursor.execute(agg_query, tuple(params))
            agg_row = cursor.fetchone()
            total_records = int(agg_row["total"]) if agg_row and agg_row["total"] is not None else 0

            # Consulta paginada
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
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM coletas WHERE id = ?", (coleta_id,))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def delete_coletas_batch(coleta_ids: List[int]) -> int:
        if not coleta_ids:
            return 0
        conn = get_db()
        cursor = conn.cursor()
        try:
            placeholders = ",".join(["?"] * len(coleta_ids))
            query = f"DELETE FROM coletas WHERE id IN ({placeholders})"
            cursor.execute(query, tuple(coleta_ids))
            conn.commit()
            return cursor.rowcount if cursor.rowcount is not None else 0
        finally:
            conn.close()