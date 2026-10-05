import math
from typing import Dict, Any

class AtmosphericPhysics:
    """
    Motor físico meteorológico para cálculo e enriquecimento psicrométrico,
    termodinâmico e probabilístico de precipitação e dessecação ambiental.
    Compatível com sensores DHT11/DHT22/BME280.
    """

    @staticmethod
    def kelvin(temp_c: float) -> float:
        """Converte temperatura de Celsius para Kelvin."""
        return round(temp_c + 273.15, 2)

    @staticmethod
    def saturation_vapor_pressure(temp_c: float) -> float:
        """
        Calcula a Pressão de Vapor de Saturação (Es) em hPa (mbar)
        utilizando a equação ampliada de Magnus-Tetens.
        Válida para a faixa de -45°C <= T <= 60°C.
        """
        a = 6.1078
        b = 17.27
        c = 237.3
        es = a * math.exp((b * temp_c) / (c + temp_c))
        return round(es, 3)

    @staticmethod
    def actual_vapor_pressure(temp_c: float, rh: float) -> float:
        """
        Calcula a Pressão Real de Vapor de Água (Ea) a partir da saturação
        e da Umidade Relativa: Ea = Es * (RH / 100).
        """
        es = AtmosphericPhysics.saturation_vapor_pressure(temp_c)
        ea = es * (max(0.0, min(100.0, rh)) / 100.0)
        return round(ea, 3)

    @staticmethod
    def dew_point(temp_c: float, rh: float) -> float:
        """
        Calcula a Temperatura do Ponto de Orvalho (Td em °C)
        invertendo a relação termodinâmica de Magnus-Tetens.
        """
        b = 17.27
        c = 237.3
        rh_clamped = max(rh, 1e-4)
        alpha = ((b * temp_c) / (c + temp_c)) + math.log(rh_clamped / 100.0)
        dp = (c * alpha) / (b - alpha)
        return round(dp, 2)

    @staticmethod
    def absolute_humidity(temp_c: float, rh: float) -> float:
        """
        Calcula a Umidade Absoluta / Densidade de Vapor (AH em g/m³)
        derivada da equação universal dos gases perfeitos:
        AH = (216.7 * Ea) / (T + 273.15), com Ea em hPa.
        """
        ea = AtmosphericPhysics.actual_vapor_pressure(temp_c, rh)
        t_k = temp_c + 273.15
        ah = (216.7 * ea) / t_k
        return round(ah, 3)

    @staticmethod
    def vpd_vapor_pressure_deficit(temp_c: float, rh: float) -> float:
        """
        Déficit de Pressão de Vapor (VPD em kPa).
        Representa a força secante da atmosfera e a taxa de evapotranspiração potencial.
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

        # Regressão polinomial completa de Rothfusz
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

        # Ajuste de correção em baixa umidade
        if rh < 13.0 and 80.0 <= t_f <= 112.0:
            adjustment = ((13.0 - rh) / 4.0) * math.sqrt(max(0.0, (17.0 - abs(t_f - 95.0)) / 17.0))
            hi -= adjustment
        # Ajuste de correção em umidade saturada
        elif rh > 85.0 and 80.0 <= t_f <= 87.0:
            adjustment = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
            hi += adjustment

        return round((hi - 32.0) / 1.8, 2)

    @staticmethod
    def rain_probability_estimate(temp_c: float, rh: float, dew_p: float) -> float:
        """
        Estimador empírico probabilístico de precipitação local (%) baseado
        na proximidade da depressão do ponto de orvalho (T - Td), saturação relativa (RH)
        e estabilidade da massa de ar térmica.
        """
        depression = max(0.0, temp_c - dew_p)

        # 1. Proximidade de Saturação (depressão < 2.5°C indica condensação iminente)
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

        # 2. Peso da Umidade Relativa Real
        rh_weight = (rh / 100.0) ** 2

        # 3. Probabilidade Composta
        prob = (sat_score * 0.65) + (rh * 0.35 * rh_weight)

        # Limitação lógica de 0 a 99%
        prob = max(1.0, min(98.5, prob))
        return round(prob, 1)

    @staticmethod
    def aridity_drought_index(temp_c: float, rh: float, vpd_kpa: float) -> float:
        """
        Índice de Secura / Estresse Hídrico Atmosférico (Escala 0 a 100%).
        Altas temperaturas combinadas com baixa umidade e elevado VPD aceleram
        o ressecamento ambiental e desidratação da pele e mucosas.
        """
        # Fator de déficit de umidade
        rh_deficit = max(0.0, (100.0 - rh) / 100.0)

        # Fator de sobreaquecimento térmico
        thermal_stress = max(0.0, (temp_c - 20.0) / 25.0)

        # Fator evaporativo do VPD (VPD > 2.0 kPa indica aridez severa)
        vpd_factor = min(1.0, vpd_kpa / 2.5)

        drought = (rh_deficit * 0.45 + thermal_stress * 0.25 + vpd_factor * 0.30) * 100.0
        drought = max(0.0, min(100.0, drought))
        return round(drought, 1)

    @classmethod
    def compute_all(cls, temp_c: float, rh: float) -> Dict[str, Any]:
        """
        Processa e retorna todas as métricas psicrométricas, bioclimáticas
        e preditivas simultaneamente sem alterar contratos existentes.
        """
        dp = cls.dew_point(temp_c, rh)
        vpd = cls.vpd_vapor_pressure_deficit(temp_c, rh)
        rain_prob = cls.rain_probability_estimate(temp_c, rh, dp)
        drought = cls.aridity_drought_index(temp_c, rh, vpd)

        return {
            "temperatura": round(temp_c, 2),
            "umidade": round(rh, 2),
            "temperatura_kelvin": cls.kelvin(temp_c),
            "pressao_vapor_sat": cls.saturation_vapor_pressure(temp_c),
            "pressao_vapor_real": cls.actual_vapor_pressure(temp_c, rh),
            "ponto_orvalho": dp,
            "umidade_absoluta": cls.absolute_humidity(temp_c, rh),
            "indice_calor": cls.heat_index(temp_c, rh),
            "vpd_kpa": vpd,
            "probabilidade_chuva": rain_prob,
            "indice_secura": drought
        }