"""
Servidor de Aplicação Flask - Projeto Estação Ambiental Atalaia
Fornece a interface visual, endpoints de API REST, filtros temporais e exportação tabular.
"""

import io
import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file, Response

from database import init_db, get_db_connection, DB_PATH
from statistics_engine import processar_estatisticas_completas
from sync import executar_sincronizacao, ESP_BASE_URL
import requests

app = Flask(__name__)
init_db()

def carregar_dataframe(filtro_inicio=None, filtro_fim=None, limite=None):
    query = "SELECT * FROM registros WHERE 1=1"
    params = []

    if filtro_inicio:
        query += " AND timestamp >= ?"
        params.append(filtro_inicio)
    if filtro_fim:
        query += " AND timestamp <= ?"
        params.append(filtro_fim)

    query += " ORDER BY timestamp ASC"

    if limite:
        query += f" LIMIT {int(limite)}"

    with get_db_connection() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    return df

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def api_status():
    esp_online = False
    esp_pending = 0
    try:
        r = requests.get(f"{ESP_BASE_URL}/api/live", timeout=2.0)
        if r.status_code == 200:
            esp_online = True
            esp_pending = r.json().get('pending', 0)
    except Exception:
        esp_online = False

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*), MAX(timestamp) FROM registros")
        total, ultimo_ts = c.fetchone()
        
        c.execute("SELECT executado_em, status FROM sync_history ORDER BY id DESC LIMIT 1")
        last_sync = c.fetchone()

    return jsonify({
        "esp32_conectada": esp_online,
        "registros_pendentes_esp32": esp_pending,
        "total_registros_sqlite": total or 0,
        "ultimo_registro_timestamp": ultimo_ts or "--",
        "ultima_sincronizacao": dict(last_sync) if last_sync else {"executado_em": "--", "status": "Nenhuma"}
    })

@app.route('/api/dados', methods=['GET'])
def api_dados():
    inicio = request.args.get('inicio')
    fim = request.args.get('fim')
    df = carregar_dataframe(inicio, fim)
    
    if df.empty:
        return jsonify([])
    
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/ultimos', methods=['GET'])
def api_ultimos():
    n = request.args.get('n', default=50, type=int)
    with get_db_connection() as conn:
        df = pd.read_sql_query(f"SELECT * FROM registros ORDER BY timestamp DESC LIMIT {n}", conn)
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/estatisticas', methods=['GET'])
def api_estatisticas():
    inicio = request.args.get('inicio')
    fim = request.args.get('fim')
    df = carregar_dataframe(inicio, fim)
    metricas = processar_estatisticas_completas(df)
    return jsonify(metricas)

@app.route('/api/sincronizar', methods=['POST'])
def api_sincronizar():
    resultado = executar_sincronizacao()
    return jsonify(resultado)

@app.route('/api/exportar/csv', methods=['GET'])
def exportar_csv():
    inicio = request.args.get('inicio')
    fim = request.args.get('fim')
    df = carregar_dataframe(inicio, fim)
    
    csv_bytes = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=atalaia_dados.csv"}
    )

@app.route('/api/exportar/excel', methods=['GET'])
def exportar_excel():
    inicio = request.args.get('inicio')
    fim = request.args.get('fim')
    df = carregar_dataframe(inicio, fim)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Registros')
    output.seek(0)

    return send_file(
        output,
        download_name="atalaia_dados.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route('/api/exportar/db', methods=['GET'])
def exportar_db():
    if os.path.exists(DB_PATH):
        return send_file(DB_PATH, download_name="atalaia.db", as_attachment=True)
    return jsonify({"erro": "Banco de dados nao localizado."}), 404

if __name__ == '__main__':
    print("=================================================================")
    print(" ESTACAO ATALAIA - SERVIDOR FLASK & ENGINE ESTATISTICA INICIADOS ")
    print(" Acesse pelo navegador: http://localhost:5000                   ")
    print("=================================================================")
    app.run(host='0.0.0.0', port=5000, debug=False)