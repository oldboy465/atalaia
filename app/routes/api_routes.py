from typing import Any, Dict, List, cast
import math
from flask import Blueprint, jsonify, request
import pandas as pd
from app.services.esp_service import ESPService
from app.services.analytics_engine import AnalyticsEngine
from app.services.physics_engine import AtmosphericPhysics
from app.models.data_model import DataModel

api_bp = Blueprint('api', __name__)

# -------------------------------------------------------------
# TABELA CRÍTICA t-STUDENT (AUTOCONTIDA PARA INTERVALOS DE CONFIANÇA)
# -------------------------------------------------------------
def get_t_critical(df_degrees: int, confidence: float = 0.95) -> float:
    if df_degrees <= 0:
        return 1.960 if confidence == 0.95 else 2.576

    t_table_95 = {
        1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
        6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        12: 2.179, 15: 2.131, 20: 2.086, 25: 2.060, 30: 2.042,
        40: 2.021, 60: 2.000, 80: 1.990, 100: 1.984, 120: 1.980
    }

    t_table_99 = {
        1: 63.657, 2: 9.925, 3: 5.841, 4: 4.604, 5: 4.032,
        6: 3.707, 7: 3.499, 8: 3.355, 9: 3.250, 10: 3.169,
        12: 3.055, 15: 2.947, 20: 2.845, 25: 2.787, 30: 2.750,
        40: 2.704, 60: 2.660, 80: 2.639, 100: 2.626, 120: 2.617
    }

    ref_table = t_table_95 if confidence == 0.95 else t_table_99
    z_limit = 1.960 if confidence == 0.95 else 2.576

    if df_degrees in ref_table:
        return ref_table[df_degrees]

    if df_degrees > 120:
        return z_limit

    chaves = sorted(ref_table.keys())
    for i in range(len(chaves) - 1):
        if chaves[i] < df_degrees < chaves[i + 1]:
            x0, x1 = chaves[i], chaves[i + 1]
            y0, y1 = ref_table[x0], ref_table[x1]
            return round(y0 + (y1 - y0) * ((df_degrees - x0) / (x1 - x0)), 3)

    return z_limit

# -------------------------------------------------------------
# ROTAS DE TELEMETRIA, CONTROLE E ENERGIA ESP32 (192.168.4.1)
# -------------------------------------------------------------
@api_bp.route('/esp/status', methods=['GET'])
def esp_status():
    status = ESPService.ping()
    if status.get('online'):
        # Enriquecimento com IAQ em tempo real caso venha mq135_raw
        t = float(status.get('temperature', 0.0))
        h = float(status.get('humidity', 0.0))
        mq = int(status.get('mq135_raw', 0))
        iaq_info = AtmosphericPhysics.calculate_iaq(mq, t, h)
        status['iaq_indice'] = iaq_info['iaq']
        status['ppm_co2'] = iaq_info['ppm_co2']
        status['iaq_classificacao'] = iaq_info['classificacao']
        status['iaq_cor'] = iaq_info['cor']
    return jsonify(status)

@api_bp.route('/esp/wakeup', methods=['POST'])
def esp_wakeup():
    success = ESPService.wakeup()
    if success:
        return jsonify({'message': 'Sinal de despertar emitido com sucesso ao nó sensorial.', 'online': True}), 200
    return jsonify({
        'message': 'Tentativa de despertar enviada. Se o nó estiver desligado, pressione RST físico ou conecte ao AP "atalaia1".',
        'online': False
    }), 200

@api_bp.route('/esp/extract', methods=['POST'])
def esp_extract():
    payload: Dict[str, Any] = request.get_json() or {}
    local_nome = str(payload.get('local_nome', '')).strip()
    raw_desc = payload.get('local_descricao')
    local_desc = str(raw_desc).strip() if raw_desc is not None else None

    raw_lat = payload.get('latitude')
    raw_lng = payload.get('longitude')
    lat = float(raw_lat) if raw_lat is not None and str(raw_lat).strip() != '' else None
    lng = float(raw_lng) if raw_lng is not None and str(raw_lng).strip() != '' else None

    if not local_nome:
        return jsonify({'error': 'O nome do local é obrigatório.'}), 400

    try:
        records = ESPService.extract_and_parse()
        if not records:
            return jsonify({'message': 'ESP32 sem novos registros no buffer.', 'count': 0}), 200

        local_id = DataModel.get_or_create_local(local_nome, local_desc, lat, lng)
        inserted = DataModel.insert_batch_coletas(local_id, records)

        ESPService.clear_buffer()

        return jsonify({'message': 'Extração concluída com sucesso.', 'count': inserted, 'local_id': local_id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/esp/shutdown', methods=['POST'])
def esp_shutdown():
    success = ESPService.shutdown()
    if success:
        return jsonify({'message': 'Comando de suspensão/economia enviado com sucesso.'}), 200
    return jsonify({'error': 'Falha ao comunicar com o nó ESP32.'}), 502

# -------------------------------------------------------------
# ROTAS DE GESTÃO E CONSULTAS PAGINADAS
# -------------------------------------------------------------
@api_bp.route('/coletas', methods=['GET'])
def get_coletas():
    local_id_param = request.args.get('local_id', type=int)
    limit = request.args.get('limit', default=500, type=int)
    dt_inicio = request.args.get('data_inicio')
    dt_fim = request.args.get('data_fim')
    coletas = DataModel.list_coletas(local_id=local_id_param, limit=limit, data_inicio=dt_inicio, data_fim=dt_fim)
    
    for c in coletas:
        t = float(c.get('temperatura', 0.0))
        h = float(c.get('umidade', 0.0))
        mq = int(c.get('mq135_raw', 0))
        dp = float(c.get('ponto_orvalho', AtmosphericPhysics.dew_point(t, h)))
        vpd = AtmosphericPhysics.vpd_vapor_pressure_deficit(t, h)
        hi = float(c.get('indice_calor', AtmosphericPhysics.heat_index(t, h)))
        
        iaq_val = float(c.get('iaq_indice', AtmosphericPhysics.calculate_iaq(mq, t, h)['iaq']))
        
        c['vpd_kpa'] = vpd
        c['probabilidade_chuva'] = AtmosphericPhysics.rain_probability_estimate(t, h, dp)
        c['indice_secura'] = AtmosphericPhysics.aridity_drought_index(t, h, vpd)
        c['aqsi_estresse'] = AtmosphericPhysics.calculate_aqsi(t, h, hi, vpd, iaq_val)
        mold = AtmosphericPhysics.mold_risk_indicator(t, h, mq)
        c['risco_bolor'] = mold['risco_percentual']
        c['status_bolor'] = mold['status']

    return jsonify(coletas)

@api_bp.route('/coletas/paginadas', methods=['GET'])
def get_coletas_paginadas():
    local_id_param = request.args.get('local_id', type=int)
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=20, type=int)
    dt_inicio = request.args.get('data_inicio')
    dt_fim = request.args.get('data_fim')
    search = request.args.get('search')

    result = DataModel.list_coletas_paginadas(
        local_id=local_id_param,
        page=page,
        per_page=per_page,
        data_inicio=dt_inicio,
        data_fim=dt_fim,
        search=search
    )

    for r in result.get('records', []):
        t = float(r.get('temperatura', 0.0))
        h = float(r.get('umidade', 0.0))
        mq = int(r.get('mq135_raw', 0))
        dp = float(r.get('ponto_orvalho', AtmosphericPhysics.dew_point(t, h)))
        vpd = AtmosphericPhysics.vpd_vapor_pressure_deficit(t, h)
        hi = float(r.get('indice_calor', AtmosphericPhysics.heat_index(t, h)))
        iaq_val = float(r.get('iaq_indice', AtmosphericPhysics.calculate_iaq(mq, t, h)['iaq']))

        r['vpd_kpa'] = vpd
        r['probabilidade_chuva'] = AtmosphericPhysics.rain_probability_estimate(t, h, dp)
        r['indice_secura'] = AtmosphericPhysics.aridity_drought_index(t, h, vpd)
        r['aqsi_estresse'] = AtmosphericPhysics.calculate_aqsi(t, h, hi, vpd, iaq_val)
        mold = AtmosphericPhysics.mold_risk_indicator(t, h, mq)
        r['risco_bolor'] = mold['risco_percentual']
        r['status_bolor'] = mold['status']

    return jsonify(result)

@api_bp.route('/coletas/<int:coleta_id>', methods=['PUT'])
def update_coleta(coleta_id: int):
    data: Dict[str, Any] = request.get_json() or {}
    novo_timestamp = data.get('coletado_em')
    if not novo_timestamp:
        return jsonify({'error': 'Campo coletado_em é obrigatório.'}), 400

    temp = float(data['temperatura']) if 'temperatura' in data and data['temperatura'] is not None else None
    hum = float(data['umidade']) if 'umidade' in data and data['umidade'] is not None else None
    mq = int(data['mq135_raw']) if 'mq135_raw' in data and data['mq135_raw'] is not None else None

    DataModel.update_coleta_inline(
        coleta_id=coleta_id,
        novo_timestamp=str(novo_timestamp),
        temp=temp,
        hum=hum,
        mq=mq
    )
    return jsonify({'message': 'Registro atualizado com sucesso.'}), 200

@api_bp.route('/coletas/<int:coleta_id>', methods=['DELETE'])
def delete_coleta(coleta_id: int):
    DataModel.delete_coleta(coleta_id)
    return jsonify({'message': 'Registro excluído com sucesso.'}), 200

@api_bp.route('/coletas/batch-delete', methods=['POST'])
def delete_coletas_batch():
    data: Dict[str, Any] = request.get_json() or {}
    ids = data.get('ids', [])
    if not ids or not isinstance(ids, list):
        return jsonify({'error': 'Nenhum ID informado para exclusão.'}), 400

    int_ids = [int(i) for i in ids]
    deleted_count = DataModel.delete_coletas_batch(int_ids)
    return jsonify({'message': f'{deleted_count} registros excluídos com sucesso.', 'count': deleted_count}), 200

@api_bp.route('/locais', methods=['GET'])
def get_locais():
    only_with_data = request.args.get('with_data', default='true').lower() in ('true', '1')
    return jsonify(DataModel.list_locais(only_with_data=only_with_data))

@api_bp.route('/locais/geo', methods=['GET'])
def get_locais_geo():
    return jsonify(DataModel.list_locais_geo())

@api_bp.route('/locais/<int:local_id>', methods=['PUT'])
def update_local(local_id: int):
    data: Dict[str, Any] = request.get_json() or {}
    nome = data.get('nome')
    raw_desc = data.get('descricao')
    descricao = str(raw_desc).strip() if raw_desc is not None else None

    raw_lat = data.get('latitude')
    raw_lng = data.get('longitude')
    lat = float(raw_lat) if raw_lat is not None and str(raw_lat).strip() != '' else None
    lng = float(raw_lng) if raw_lng is not None and str(raw_lng).strip() != '' else None

    if not nome:
        return jsonify({'error': 'Nome do local é obrigatório.'}), 400

    DataModel.update_local(local_id, str(nome), descricao, lat, lng)
    return jsonify({'message': 'Local atualizado com sucesso.'}), 200

# -------------------------------------------------------------
# ESTATÍSTICA DESCRITIVA ROBUSTA (INCLUINDO QUALIDADE DO AR)
# -------------------------------------------------------------
@api_bp.route('/analytics/descriptive', methods=['GET'])
def get_descriptive_stats():
    local_id_param = request.args.get('local_id', type=int)
    dt_inicio = request.args.get('data_inicio')
    dt_fim = request.args.get('data_fim')

    rows = DataModel.list_coletas(local_id=local_id_param, limit=10000, data_inicio=dt_inicio, data_fim=dt_fim)
    if not rows:
        return jsonify({'count': 0, 'stats': {}}), 200

    df = pd.DataFrame(rows)
    variables = [
        'temperatura', 'umidade', 'indice_calor', 'ponto_orvalho',
        'umidade_absoluta', 'pressao_vapor_real', 'mq135_raw', 'ppm_co2', 'iaq_indice'
    ]
    result: Dict[str, Any] = {}

    for var in variables:
        if var not in df.columns:
            continue

        series = pd.to_numeric(df[var], errors='coerce').dropna()
        n = int(series.count())
        if n == 0:
            continue

        mean_val = float(series.mean())
        median_val = float(series.median())
        min_val = float(series.min())
        max_val = float(series.max())
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        p10 = float(series.quantile(0.10))
        p90 = float(series.quantile(0.90))
        var_val = float(series.var(ddof=1)) if n > 1 else 0.0
        sd_val = float(series.std(ddof=1)) if n > 1 else 0.0
        cv_val = float((sd_val / mean_val) * 100) if mean_val != 0 else 0.0

        if n > 1 and sd_val > 0:
            se = sd_val / math.sqrt(n)
            df_deg = n - 1
            t_crit_95 = get_t_critical(df_deg, 0.95)
            t_crit_99 = get_t_critical(df_deg, 0.99)
            ic_95_low = round(mean_val - t_crit_95 * se, 2)
            ic_95_high = round(mean_val + t_crit_95 * se, 2)
            ic_99_low = round(mean_val - t_crit_99 * se, 2)
            ic_99_high = round(mean_val + t_crit_99 * se, 2)
        else:
            ic_95_low = ic_95_high = round(mean_val, 2)
            ic_99_low = ic_99_high = round(mean_val, 2)

        result[var] = {
            "n": n,
            "media": round(mean_val, 2),
            "mediana": round(median_val, 2),
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "p10": round(p10, 2),
            "p90": round(p90, 2),
            "variancia": round(var_val, 3),
            "dp": round(sd_val, 2),
            "cv": round(cv_val, 2),
            "ic_95": f"[{ic_95_low}, {ic_95_high}]",
            "ic_99": f"[{ic_99_low}, {ic_99_high}]"
        }

    return jsonify({'count': len(df), 'stats': result}), 200

# -------------------------------------------------------------
# ROTAS ANALÍTICAS E MACHINE LEARNING SUPERVISIONADO E AR
# -------------------------------------------------------------
@api_bp.route('/analytics/train', methods=['POST'])
def train_model():
    payload: Dict[str, Any] = request.get_json() or {}
    raw_local_id = payload.get('local_id')
    local_id = int(raw_local_id) if raw_local_id is not None else None

    target = str(payload.get('target', 'temperatura'))
    features = cast(List[str], payload.get('features', ['umidade', 'indice_calor']))
    model_type = str(payload.get('model_type', 'ols'))
    hyperparams = cast(Dict[str, Any], payload.get('hyperparams', {}))

    raw_data = DataModel.list_coletas(local_id=local_id, limit=3000)
    if len(raw_data) < 10:
        return jsonify({'error': 'Volume insuficiente de dados no local selecionado para ajuste de modelo.'}), 400

    df = pd.DataFrame(raw_data)
    try:
        results = AnalyticsEngine.train_supervised_model(
            df=df,
            target_col=target,
            feature_cols=features,
            model_type=model_type,
            **hyperparams
        )
        return jsonify(results), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@api_bp.route('/analytics/forecast', methods=['POST'])
def forecast():
    payload: Dict[str, Any] = request.get_json() or {}
    raw_local_id = payload.get('local_id')
    local_id = int(raw_local_id) if raw_local_id is not None else None

    target = str(payload.get('target', 'temperatura'))
    lags = int(payload.get('lags', 5))
    steps = int(payload.get('steps', 20))

    raw_data = DataModel.list_coletas(local_id=local_id, limit=1500)
    if not raw_data:
        return jsonify({'error': 'Nenhum dado encontrado para projeção temporal.'}), 400

    df = pd.DataFrame(raw_data).sort_values(by='coletado_em')
    try:
        results = AnalyticsEngine.forecast_autoregressive(
            series=df[target],
            lags=lags,
            steps=steps
        )
        return jsonify(results), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400