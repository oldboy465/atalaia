"""
Servidor de Aplicação Flask - Projeto Estação Ambiental Atalaia
Suporte a filtragem dinâmica tripla (Data, Hora e Local), exclusão em lote e exportação.
"""

import io
import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file, Response

from database import (
    init_db, 
    get_db_connection, 
    DB_PATH, 
    obter_locais_unicos,
    excluir_registros
)
from statistics_engine import processar_estatisticas_completas
from sync import executar_sincronizacao, ESP_BASE_URL
import requests

app = Flask(__name__)
init_db()

def carregar_dataframe(data_inicio=None, data_fim=None, hora_inicio=None, hora_fim=None, local=None, limite=None):
    query = "SELECT * FROM registros WHERE 1=1"
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

    query += " ORDER BY timestamp ASC"

    if limite:
        query += f" LIMIT {int(limite)}"

    with get_db_connection() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    return df

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/locais', methods=['GET'])
def api_locais():
    return jsonify(obter_locais_unicos())

@app.route('/api/status', methods=['GET'])
def api_status():
    esp_online = False
    esp_pending = 0
    try:
        r = requests.get(f"{ESP_BASE_URL}/api/live", timeout=1.5)
        if r.status_code == 200:
            esp_online = True
            esp_pending = r.json().get('pending', 0)
    except Exception:
        esp_online = False

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*), MAX(timestamp) FROM registros")
        total, ultimo_ts = c.fetchone()
        
        c.execute("SELECT executado_em, local, status FROM sync_history ORDER BY id DESC LIMIT 1")
        last_sync = c.fetchone()

    return jsonify({
        "esp32_conectada": esp_online,
        "registros_pendentes_esp32": esp_pending,
        "total_registros_sqlite": total or 0,
        "ultimo_registro_timestamp": ultimo_ts or "--",
        "ultima_sincronizacao": dict(last_sync) if last_sync else {"executado_em": "--", "local": "--", "status": "Nenhuma"}
    })

@app.route('/api/dados', methods=['GET'])
def api_dados():
    df = carregar_dataframe(
        data_inicio=request.args.get('data_inicio'),
        data_fim=request.args.get('data_fim'),
        hora_inicio=request.args.get('hora_inicio'),
        hora_fim=request.args.get('hora_fim'),
        local=request.args.get('local')
    )
    if df.empty:
        return jsonify([])
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/ultimos', methods=['GET'])
def api_ultimos():
    n = request.args.get('n', default=100, type=int)
    local = request.args.get('local')
    query = "SELECT * FROM registros"
    params = []
    if local and local != 'TODOS':
        query += " WHERE local = ?"
        params.append(local)
    query += f" ORDER BY timestamp DESC LIMIT {n}"

    with get_db_connection() as conn:
        df = pd.read_sql_query(query, conn, params=params)
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/estatisticas', methods=['GET'])
def api_estatisticas():
    df = carregar_dataframe(
        data_inicio=request.args.get('data_inicio'),
        data_fim=request.args.get('data_fim'),
        hora_inicio=request.args.get('hora_inicio'),
        hora_fim=request.args.get('hora_fim'),
        local=request.args.get('local')
    )
    metricas = processar_estatisticas_completas(df)
    return jsonify(metricas)

@app.route('/api/sincronizar', methods=['POST'])
def api_sincronizar():
    dados = request.get_json(silent=True) or {}
    local_nome = dados.get('local', request.form.get('local', 'Sede Principal'))
    resultado = executar_sincronizacao(local_nome=local_nome)
    return jsonify(resultado)

@app.route('/api/excluir', methods=['POST'])
def api_excluir():
    dados = request.get_json(silent=True) or {}
    limpar_tudo = dados.get('limpar_tudo', False)
    
    if limpar_tudo:
        deletados = excluir_registros()
        return jsonify({"sucesso": True, "deletados": deletados, "mensagem": f"Banco limpo integralmente! {deletados} registros apagados."})
    
    deletados = excluir_registros(
        data_inicio=dados.get('data_inicio'),
        data_fim=dados.get('data_fim'),
        hora_inicio=dados.get('hora_inicio'),
        hora_fim=dados.get('hora_fim'),
        local=dados.get('local')
    )
    return jsonify({"sucesso": True, "deletados": deletados, "mensagem": f"{deletados} registros removidos conforme o filtro aplicado."})

@app.route('/api/exportar/csv', methods=['GET'])
def exportar_csv():
    df = carregar_dataframe(
        data_inicio=request.args.get('data_inicio'),
        data_fim=request.args.get('data_fim'),
        hora_inicio=request.args.get('hora_inicio'),
        hora_fim=request.args.get('hora_fim'),
        local=request.args.get('local')
    )
    csv_bytes = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=atalaia_filtrado.csv"}
    )

@app.route('/api/exportar/excel', methods=['GET'])
def exportar_excel():
    df = carregar_dataframe(
        data_inicio=request.args.get('data_inicio'),
        data_fim=request.args.get('data_fim'),
        hora_inicio=request.args.get('hora_inicio'),
        hora_fim=request.args.get('hora_fim'),
        local=request.args.get('local')
    )
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Registros')
    output.seek(0)

    return send_file(
        output,
        download_name="atalaia_filtrado.xlsx",
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
    print(" ESTACAO ATALAIA - MOTOR ESTATISTICO DINAMICO MULTI-LOCAL ATIVO  ")
    print(" Acesse pelo navegador: http://localhost:5000                   ")
    print("=================================================================")
    app.run(host='0.0.0.0', port=5000, debug=False)