"""
Motor Matemático, Meteorológico e Estatístico Avançado - Estação Atalaia
Calcula parâmetros univariados, bivariados, psicrométricos e bioclimáticos.
"""

import math
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression

def calcular_ponto_orvalho(temperatura, umidade):
    """Aproximação de Magnus-Tetens (Alduchov & Eskridge, 1996)."""
    if umidade <= 0.0:
        return temperatura
    a, b = 17.27, 237.7
    alpha = ((a * temperatura) / (b + temperatura)) + math.log(umidade / 100.0)
    return round((b * alpha) / (a - alpha), 2)

def calcular_sensacao_termica(temperatura, umidade):
    """Algoritmo Heat Index do National Weather Service (NOAA / Rothfusz)."""
    T_f = (temperatura * 9.0 / 5.0) + 32.0
    RH = umidade

    hi_f = 0.5 * (T_f + 61.0 + ((T_f - 68.0) * 1.2) + (RH * 0.094))

    if (hi_f + T_f) / 2.0 >= 80.0:
        hi_f = (-42.379 + 
                2.04901523 * T_f + 
                10.14333127 * RH - 
                0.22475541 * T_f * RH - 
                0.00683783 * (T_f ** 2) - 
                0.05481717 * (RH ** 2) + 
                0.00122874 * (T_f ** 2) * RH + 
                0.00085282 * T_f * (RH ** 2) - 
                0.00000199 * (T_f ** 2) * (RH ** 2))
        
        if RH < 13.0 and 80.0 <= T_f <= 112.0:
            hi_f -= ((13.0 - RH) / 4.0) * math.sqrt((17.0 - abs(T_f - 95.0)) / 17.0)
        elif RH > 85.0 and 80.0 <= T_f <= 87.0:
            hi_f += ((RH - 85.0) / 10.0) * ((87.0 - T_f) / 5.0)

    return round((hi_f - 32.0) * 5.0 / 9.0, 2)

def calcular_pressao_vapor(temperatura, umidade):
    """Calcula a pressão de vapor d'água parcial e de saturação (hPa) via fórmula de Tetens."""
    es = 6.1078 * (10.0 ** ((7.5 * temperatura) / (237.3 + temperatura)))
    e = es * (umidade / 100.0)
    return round(e, 2), round(es, 2)

def calcular_umidade_absoluta(temperatura, umidade):
    """Calcula a densidade de vapor d'água em gramas por metro cúbico (g/m³)."""
    e, _ = calcular_pressao_vapor(temperatura, umidade)
    # rho = (e * 100) / (Rv * T_kelvin), Rv = 461.5 J/(kg·K) => e * 216.7 / (T + 273.15)
    t_k = temperatura + 273.15
    ah = (e * 216.7) / t_k
    return round(ah, 2)

def calcular_entalpia(temperatura, umidade):
    """Calcula a entalpia específica do ar úmido em kJ/kg (P = 1013.25 hPa ao nível do mar)."""
    e, _ = calcular_pressao_vapor(temperatura, umidade)
    p_atm = 1013.25
    # Razão de mistura w = 0.622 * e / (p - e)
    w = (0.622 * e) / max(1.0, (p_atm - e))
    # h = 1.006 * T + w * (2501 + 1.86 * T)
    h = (1.006 * temperatura) + (w * (2501.0 + 1.86 * temperatura))
    return round(h, 2)

def calcular_indice_thom(temperatura, umidade):
    """Índice de Desconforto Térmico de Thom: DI = T - (0.55 - 0.0055*RH)*(T - 14.5)."""
    di = temperatura - (0.55 - 0.0055 * umidade) * (temperatura - 14.5)
    return round(di, 2)

def classificar_thom(di):
    if di < 21.0:
        return "Sem desconforto"
    elif di < 25.0:
        return "Menos de 50% da população sente desconforto"
    elif di < 27.0:
        return "Mais de 50% da população sente desconforto"
    elif di < 29.0:
        return "Maioria em desconforto / Estresse térmico"
    else:
        return "Estado de emergência médica / Estresse severo"

def analisar_vetor(vetor):
    """Análise estatística descritiva completa univariada com métricas paramétricas e robustas."""
    arr = np.array(vetor, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = len(arr)
    
    if n == 0:
        return {}

    media = float(np.mean(arr))
    mediana = float(np.median(arr))
    minimo = float(np.min(arr))
    maximo = float(np.max(arr))
    amplitude = maximo - minimo
    
    variancia = float(np.var(arr, ddof=1)) if n > 1 else 0.0
    desvio_padrao = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    coef_variacao = (desvio_padrao / media * 100.0) if media != 0 else 0.0

    # MAD (Median Absolute Deviation)
    mad = float(np.median(np.abs(arr - mediana)))

    q25 = float(np.percentile(arr, 25))
    q75 = float(np.percentile(arr, 75))
    iqr = q75 - q25

    p10 = float(np.percentile(arr, 10))
    p90 = float(np.percentile(arr, 90))

    moda_res = stats.mode(arr, keepdims=True)
    moda = float(moda_res.mode[0]) if len(moda_res.mode) > 0 else media

    assimetria = float(stats.skew(arr)) if n > 2 else 0.0
    curtose = float(stats.kurtosis(arr)) if n > 3 else 0.0

    return {
        "n": n,
        "media": round(media, 2),
        "mediana": round(mediana, 2),
        "minimo": round(minimo, 2),
        "maximo": round(maximo, 2),
        "amplitude": round(amplitude, 2),
        "variancia": round(variancia, 3),
        "desvio_padrao": round(desvio_padrao, 2),
        "coef_variacao": round(coef_variacao, 2),
        "mad": round(mad, 2),
        "q25": round(q25, 2),
        "q75": round(q75, 2),
        "iqr": round(iqr, 2),
        "p10": round(p10, 2),
        "p90": round(p90, 2),
        "moda": round(moda, 2),
        "assimetria": round(assimetria, 3),
        "curtose": round(curtose, 3)
    }

def regressao_linear_temporal(y_valores, intervalos_s):
    n = len(y_valores)
    if n < 2:
        return {
            "equacao": "Amostras insuficientes",
            "coef_angular": 0.0,
            "intercepto": 0.0,
            "r2": 0.0,
            "tendencia": "Indeterminada"
        }

    x = np.cumsum([0] + [intervalos_s[i] for i in range(len(intervalos_s)-1)]).reshape(-1, 1)
    y = np.array(y_valores).reshape(-1, 1)

    reg = LinearRegression().fit(x, y)
    coef_angular = float(reg.coef_[0][0])
    intercepto = float(reg.intercept_[0])
    r2 = float(reg.score(x, y))

    if coef_angular > 0.0005:
        tendencia = "Ascendente"
    elif coef_angular < -0.0005:
        tendencia = "Descendente"
    else:
        tendencia = "Estável"

    sinal = "+" if intercepto >= 0 else "-"
    equacao = f"y = {coef_angular:.5f}·t {sinal} {abs(intercepto):.2f}"

    return {
        "equacao": equacao,
        "coef_angular": round(coef_angular, 5),
        "intercepto": round(intercepto, 2),
        "r2": round(r2, 4),
        "tendencia": tendencia
    }

def processar_estatisticas_completas(df):
    if df.empty:
        return {"total_registros": 0, "status": "Sem dados"}

    temp_stats = analisar_vetor(df['temperatura'].values)
    hum_stats = analisar_vetor(df['umidade'].values)

    intervalos = df['intervalo_segundos'].values.tolist()
    reg_temp = regressao_linear_temporal(df['temperatura'].values, intervalos)
    reg_hum = regressao_linear_temporal(df['umidade'].values, intervalos)

    correlacao = float(df['temperatura'].corr(df['umidade'])) if len(df) > 1 else 0.0
    covariancia = float(df['temperatura'].cov(df['umidade'])) if len(df) > 1 else 0.0

    dp_stats = analisar_vetor(df['ponto_orvalho'].values)
    hi_stats = analisar_vetor(df['sensacao_termica'].values)
    vp_stats = analisar_vetor(df['pressao_vapor'].values)
    ah_stats = analisar_vetor(df['umidade_absoluta'].values)
    ent_stats = analisar_vetor(df['entalpia'].values)
    thom_stats = analisar_vetor(df['indice_thom'].values)

    ultima_temp = float(df['temperatura'].iloc[-1])
    ultima_hum = float(df['umidade'].iloc[-1])
    primeira_temp = float(df['temperatura'].iloc[0])
    primeira_hum = float(df['umidade'].iloc[0])

    var_temp_abs = ultima_temp - primeira_temp
    var_temp_pct = (var_temp_abs / primeira_temp * 100.0) if primeira_temp != 0 else 0.0

    razao_temp_hum = ultima_temp / ultima_hum if ultima_hum != 0 else 0.0
    delta_temp_orvalho = ultima_temp - float(df['ponto_orvalho'].iloc[-1])
    razao_amplitudes = (temp_stats['amplitude'] / hum_stats['amplitude']) if hum_stats['amplitude'] != 0 else 0.0

    tempo_total_segundos = float(df['intervalo_segundos'].sum()) - float(df['intervalo_segundos'].iloc[0])
    tempo_horas = tempo_total_segundos / 3600.0 if tempo_total_segundos > 0 else 1.0

    taxa_temp_hora = var_temp_abs / tempo_horas
    taxa_hum_hora = (ultima_hum - primeira_hum) / tempo_horas

    ultimo_thom = float(df['indice_thom'].iloc[-1])

    return {
        "total_registros": len(df),
        "tempo_monitoramento_segundos": tempo_total_segundos,
        "locais_presentes": df['local'].unique().tolist(),
        "temperatura": {
            "atual": ultima_temp,
            "descritiva": temp_stats,
            "regressao": reg_temp,
            "var_absoluta": round(var_temp_abs, 2),
            "var_percentual": round(var_temp_pct, 2),
            "taxa_por_hora": round(taxa_temp_hora, 3)
        },
        "umidade": {
            "atual": ultima_hum,
            "descritiva": hum_stats,
            "regressao": reg_hum,
            "var_absoluta": round(ultima_hum - primeira_hum, 2),
            "var_percentual": round(((ultima_hum - primeira_hum) / primeira_hum * 100.0) if primeira_hum != 0 else 0.0, 2),
            "taxa_por_hora": round(taxa_hum_hora, 3)
        },
        "bivariada": {
            "correlacao_pearson": round(correlacao, 4),
            "covariancia": round(covariancia, 4)
        },
        "ponto_orvalho": {
            "atual": float(df['ponto_orvalho'].iloc[-1]),
            "descritiva": dp_stats
        },
        "sensacao_termica": {
            "atual": float(df['sensacao_termica'].iloc[-1]),
            "descritiva": hi_stats
        },
        "psicrometria_avancada": {
            "pressao_vapor_atual": float(df['pressao_vapor'].iloc[-1]),
            "pressao_vapor_descritiva": vp_stats,
            "umidade_absoluta_atual": float(df['umidade_absoluta'].iloc[-1]),
            "umidade_absoluta_descritiva": ah_stats,
            "entalpia_atual": float(df['entalpia'].iloc[-1]),
            "entalpia_descritiva": ent_stats,
            "indice_thom_atual": ultimo_thom,
            "indice_thom_classificacao": classificar_thom(ultimo_thom),
            "indice_thom_descritiva": thom_stats
        },
        "indicadores_derivados": {
            "razao_temperatura_umidade": round(razao_temp_hum, 4),
            "diferenca_temperatura_orvalho": round(delta_temp_orvalho, 2),
            "razao_amplitudes": round(razao_amplitudes, 4)
        }
    }