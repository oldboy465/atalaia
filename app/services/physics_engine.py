import math
from typing import Dict, Any

class AtmosphericPhysics:
    """
    Motor físico meteorológico e de química de gases atmosféricos.
    Calcula parâmetros psicrométricos, bioclimáticos, probabilidade de chuva,
    estresse de secura e compensação higrotérmica com calibração analítica do MQ-135.
    """

    # Parâmetros de calibração do sensor MQ-135
    RL_LOAD_RESISTANCE = 10.0      # Resistência de carga RL em kOhms
    ADC_MAX_VALUE = 4095.0         # Resolução de 12 bits do ADC do ESP32
    V_IN = 3.3                     # Tensão de alimentação (V)
    R0_CLEAN_AIR = 76.63           # Resistência do sensor calibrada em ar puro (kOhms)
    PPM_A = 116.6020682            # Fator de escala da curva CO2
    PPM_B = -2.769034857           # Expoente angular da curva CO2

    @staticmethod
    def kelvin(temp_c: float) -> float:
        """Converte temperatura de Celsius para Kelvin."""
        return round(temp_c + 273.15, 2)

    @staticmethod
    def saturation_vapor_pressure(temp_c: float) -> float:
        """
        Calcula a Pressão de Vapor de Saturação (Es) em hPa (mbar)
        utilizando a equação ampliada de Magnus-Tetens (-45°C <= T <= 60°C).
        """
        a = 6.1078
        b = 17.27
        c = 237.3
        es = a * math.exp((b * temp_c) / (c + temp_c))
        return round(es, 3)

    @staticmethod
    def actual_vapor_pressure(temp_c: float, rh: float) -> float:
        """
        Calcula a Pressão Real de Vapor de Água (Ea) em hPa:
        Ea = Es * (RH / 100).
        """
        es = AtmosphericPhysics.saturation_vapor_pressure(temp_c)
        ea = es * (max(0.0, min(100.0, rh)) / 100.0)
        return round(ea, 3)

    @staticmethod
    def dew_point(temp_c: float, rh: float) -> float:
        """
        Calcula a Temperatura do Ponto de Orvalho (Td em °C)
        pela inversão da relação termodinâmica de Magnus-Tetens.
        Protegido contra valores nulos de umidade relativa.
        """
        b = 17.27
        c = 237.3
        rh_clamped = max(1.0, min(100.0, rh))
        alpha = ((b * temp_c) / (c + temp_c)) + math.log(rh_clamped / 100.0)
        dp = (c * alpha) / (b - alpha)
        return round(dp, 2)

    @staticmethod
    def absolute_humidity(temp_c: float, rh: float) -> float:
        """
        Calcula a Umidade Absoluta / Densidade de Vapor (AH em g/m³):
        AH = (216.7 * Ea) / (T + 273.15).
        """
        ea = AtmosphericPhysics.actual_vapor_pressure(temp_c, rh)
        t_k = temp_c + 273.15
        ah = (216.7 * ea) / t_k
        return round(ah, 3)

    @staticmethod
    def vpd_vapor_pressure_deficit(temp_c: float, rh: float) -> float:
        """
        Déficit de Pressão de Vapor (VPD em kPa).
        VPD = (Es - Ea) / 10.
        """
        es = AtmosphericPhysics.saturation_vapor_pressure(temp_c)
        ea = AtmosphericPhysics.actual_vapor_pressure(temp_c, rh)
        deficit_hpa = max(0.0, es - ea)
        return round(deficit_hpa / 10.0, 3)

    @staticmethod
    def heat_index(temp_c: float, rh: float) -> float:
        """
        Cálculo do Índice de Calor / Sensação Térmica (NOAA / Rothfusz Regression).
        Converte internamente para Fahrenheit, processa os coeficientes e retorna em °C.
        """
        t_f = temp_c * 1.8 + 32.0

        # Para condições amenas, a aproximação linear de Steadman é ideal
        hi_simple = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))
        if hi_simple < 80.0:
            return round((hi_simple - 32.0) / 1.8, 2)

        # Regressão polinomial de Rothfusz
        c1 = -42.379
        c2 = 2.04901523
        c3 = 10.14333127
        c4 = -0.22475541
        c5 = -0.00683783
        c6 = -0.05481717
        c7 = 0.00122874
        c8 = 0.00085282
        c9 = -0.00000199

        hi = (c1 + (c2 * t_f) + (c3 * rh) + (c4 * t_f * rh) +
              (c5 * t_f * t_f) + (c6 * rh * rh) + (c7 * t_f * t_f * rh) +
              (c8 * t_f * rh * rh) + (c9 * t_f * t_f * rh * rh))

        if rh < 13.0 and 80.0 <= t_f <= 112.0:
            adjustment = ((13.0 - rh) / 4.0) * math.sqrt(max(0.0, (17.0 - abs(t_f - 95.0)) / 17.0))
            hi -= adjustment
        elif rh > 85.0 and 80.0 <= t_f <= 87.0:
            adjustment = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
            hi += adjustment

        return round((hi - 32.0) / 1.8, 2)

    @staticmethod
    def rain_probability_estimate(temp_c: float, rh: float, dew_p: float) -> float:
        """
        Estimador probabilístico de precipitação local (%) baseado
        na depressão do ponto de orvalho (T - Td) e na saturação de umidade relativa.
        """
        depression = max(0.0, temp_c - dew_p)

        if depression <= 1.0:
            sat_score = 95.0
        elif depression <= 2.5:
            sat_score = 80.0 - (depression - 1.0) * 15.0
        elif depression <= 5.0:
            sat_score = 55.0 - (depression - 2.5) * 12.0
        elif depression <= 8.0:
            sat_score = 25.0 - (depression - 5.0) * 6.0
        else:
            sat_score = max(2.0, 10.0 - (depression - 8.0) * 1.5)

        rh_weight = (rh / 100.0) ** 2
        prob = (sat_score * 0.65) + (rh * 0.35 * rh_weight)
        prob = max(1.0, min(98.5, prob))
        return round(prob, 1)

    @staticmethod
    def aridity_drought_index(temp_c: float, rh: float, vpd_kpa: float) -> float:
        """
        Índice de Secura / Estresse Hídrico Atmosférico (0 a 100%).
        """
        rh_deficit = max(0.0, (100.0 - rh) / 100.0)
        thermal_stress = max(0.0, (temp_c - 20.0) / 25.0)
        vpd_factor = min(1.0, vpd_kpa / 2.5)

        drought = (rh_deficit * 0.45 + thermal_stress * 0.25 + vpd_factor * 0.30) * 100.0
        drought = max(0.0, min(100.0, drought))
        return round(drought, 1)

    # -------------------------------------------------------------
    # FÍSICA E QUÍMICA DE GASES: MQ-135 & ÍNDICES AMBIENTAIS
    # -------------------------------------------------------------
    @classmethod
    def mq135_environmental_correction_factor(cls, temp_c: float, rh: float) -> float:
        """
        Fator de correção higrotérmica COR do MQ-135 derivado da
        curva característica do datasheet (referência de calibração: 20°C e 33% RH).
        """
        cor = 1.0 + (temp_c - 20.0) * (-0.0075) + (rh - 33.0) * (-0.0035)
        return max(0.35, min(1.85, cor))

    @classmethod
    def calculate_rs_r0(cls, mq_raw: int, temp_c: float, rh: float) -> Dict[str, float]:
        """
        Calcula a resistência ôhmica do sensor (Rs), a resistência compensada e a razão Rs/R0.
        Clamp estrito de ADC para 1..4094 para evitar divisão por zero ou números negativos.
        """
        adc = max(1.0, min(cls.ADC_MAX_VALUE - 1.0, float(mq_raw)))
        rs_raw = cls.RL_LOAD_RESISTANCE * ((cls.ADC_MAX_VALUE - adc) / adc)
        cor_factor = cls.mq135_environmental_correction_factor(temp_c, rh)
        rs_compensated = rs_raw / cor_factor
        ratio = rs_compensated / cls.R0_CLEAN_AIR

        return {
            "rs_raw": round(rs_raw, 3),
            "rs_comp": round(rs_compensated, 3),
            "ratio": round(ratio, 4),
            "cor_factor": round(cor_factor, 3)
        }

    @classmethod
    def estimate_ppm_co2(cls, mq_raw: int, temp_c: float, rh: float) -> float:
        """
        Estimação analítica de CO2 equivalente em PPM pela curva calibrada.
        """
        if mq_raw <= 0:
            return 400.0

        metrics = cls.calculate_rs_r0(mq_raw, temp_c, rh)
        ratio = max(0.1, metrics["ratio"])
        try:
            ppm = cls.PPM_A * math.pow(ratio, cls.PPM_B)
            # CO2 atmosférico típico entre 400 e 5000 PPM
            ppm_calibrated = max(400.0, min(5000.0, ppm + 380.0))
            return round(ppm_calibrated, 1)
        except (ValueError, OverflowError):
            return 400.0

    @classmethod
    def calculate_iaq(cls, mq_raw: int, temp_c: float, rh: float) -> Dict[str, Any]:
        """
        Calcula o Índice Sintético de Qualidade do Ar (IAQ: 0 a 500).
        A faixa de ar limpo (400 a 450 ppm) é mapeada para 15 a 50 IAQ
        para que o mostrador exiba leitura dinâmica ativa em vez de 0.0 estático.
        """
        ppm = cls.estimate_ppm_co2(mq_raw, temp_c, rh)

        if ppm <= 450.0:
            iaq = 15.0 + ((ppm - 400.0) / 50.0) * 35.0
            classificacao = "Excelente"
            cor = "#10b981"
        elif ppm <= 700.0:
            iaq = 50.0 + ((ppm - 450.0) / 250.0) * 50.0
            classificacao = "Boa"
            cor = "#34d399"
        elif ppm <= 1000.0:
            iaq = 100.0 + ((ppm - 700.0) / 300.0) * 50.0
            classificacao = "Moderada"
            cor = "#facc15"
        elif ppm <= 1600.0:
            iaq = 150.0 + ((ppm - 1000.0) / 600.0) * 50.0
            classificacao = "Atenção"
            cor = "#fb923c"
        else:
            iaq = 200.0 + min(300.0, ((ppm - 1600.0) / 2400.0) * 300.0)
            classificacao = "Crítica"
            cor = "#f43f5e"

        return {
            "iaq": round(max(0.0, min(500.0, iaq)), 1),
            "ppm_co2": ppm,
            "classificacao": classificacao,
            "cor": cor
        }

    @classmethod
    def calculate_aqsi(cls, temp_c: float, rh: float, hi: float, vpd: float, iaq: float) -> float:
        """
        Índice Composto de Estresse Ambiental (AQSI - 0 a 100%).
        Integra estresse térmico (HI), dessecação por déficit de vapor (VPD) e saturação gasosa (IAQ).
        """
        hi_factor = min(1.0, max(0.0, (hi - 22.0) / 20.0))
        vpd_factor = min(1.0, max(0.0, vpd / 3.0))
        iaq_factor = min(1.0, max(0.0, iaq / 250.0))

        aqsi = (hi_factor * 0.35 + vpd_factor * 0.30 + iaq_factor * 0.35) * 100.0
        return round(max(0.0, min(100.0, aqsi)), 1)

    @classmethod
    def mold_risk_indicator(cls, temp_c: float, rh: float, mq_raw: int) -> Dict[str, Any]:
        """
        Indicador de Risco de Bolor e Proliferação Fúngica (0 a 100%).
        Associa umidade sustentada (RH > 65%), janela térmica ótima (20-35°C) e COVs no ar.
        """
        if rh < 65.0 or temp_c < 15.0 or temp_c > 40.0:
            risk = max(0.0, (rh / 100.0) * 15.0)
            status = "Baixo"
        else:
            rh_score = min(1.0, (rh - 65.0) / 25.0)
            temp_optimum = 1.0 - (abs(temp_c - 27.5) / 12.5)
            gas_score = min(1.0, max(0.0, (mq_raw - 1200) / 2000.0))

            risk = (rh_score * 0.50 + max(0.0, temp_optimum) * 0.30 + gas_score * 0.20) * 100.0
            
            if risk >= 75.0:
                status = "Crítico (Proliferação Acelerada)"
            elif risk >= 45.0:
                status = "Moderado / Alerta"
            else:
                status = "Baixo"

        return {
            "risco_percentual": round(max(0.0, min(100.0, risk)), 1),
            "status": status
        }

    @classmethod
    def compute_all(cls, temp_c: float, rh: float, mq_raw: int = 0) -> Dict[str, Any]:
        """
        Calcula e retorna simultaneamente todas as grandezas psicrométricas,
        bioclimáticas e químicas do ecossistema Atalaia 1.
        """
        dp = cls.dew_point(temp_c, rh)
        vpd = cls.vpd_vapor_pressure_deficit(temp_c, rh)
        hi = cls.heat_index(temp_c, rh)
        rain_prob = cls.rain_probability_estimate(temp_c, rh, dp)
        drought = cls.aridity_drought_index(temp_c, rh, vpd)
        
        iaq_data = cls.calculate_iaq(mq_raw, temp_c, rh)
        aqsi = cls.calculate_aqsi(temp_c, rh, hi, vpd, iaq_data["iaq"])
        mold_data = cls.mold_risk_indicator(temp_c, rh, mq_raw)

        return {
            "temperatura": round(temp_c, 2),
            "umidade": round(rh, 2),
            "temperatura_kelvin": cls.kelvin(temp_c),
            "pressao_vapor_sat": cls.saturation_vapor_pressure(temp_c),
            "pressao_vapor_real": cls.actual_vapor_pressure(temp_c, rh),
            "ponto_orvalho": dp,
            "umidade_absoluta": cls.absolute_humidity(temp_c, rh),
            "indice_calor": hi,
            "vpd_kpa": vpd,
            "probabilidade_chuva": rain_prob,
            "indice_secura": drought,
            "mq135_raw": int(mq_raw),
            "ppm_co2": iaq_data["ppm_co2"],
            "iaq_indice": iaq_data["iaq"],
            "iaq_classificacao": iaq_data["classificacao"],
            "iaq_cor": iaq_data["cor"],
            "aqsi_estresse": aqsi,
            "risco_bolor": mold_data["risco_percentual"],
            "status_bolor": mold_data["status"]
        }