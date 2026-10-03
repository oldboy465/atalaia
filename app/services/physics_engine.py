import math

class AtmosphericPhysics:
    """
    Motor físico para cálculo e enriquecimento de grandezas psicrométricas
    a partir de Temperatura (°C) e Umidade Relativa (%).
    """

    @staticmethod
    def kelvin(temp_c: float) -> float:
        return round(temp_c + 273.15, 2)

    @staticmethod
    def saturation_vapor_pressure(temp_c: float) -> float:
        """
        Equação de Magnus-Tetens para Es em hPa (mbar).
        Válida para -45°C <= T <= 60°C.
        """
        a = 6.1078
        b = 17.27
        c = 237.3
        es = a * math.exp((b * temp_c) / (c + temp_c))
        return round(es, 3)

    @staticmethod
    def actual_vapor_pressure(temp_c: float, rh: float) -> float:
        """
        Calcula Ea a partir de Es e umidade relativa: Ea = Es * (RH / 100).
        """
        es = AtmosphericPhysics.saturation_vapor_pressure(temp_c)
        ea = es * (rh / 100.0)
        return round(ea, 3)

    @staticmethod
    def dew_point(temp_c: float, rh: float) -> float:
        """
        Ponto de Orvalho Exato (°C) invertendo a relação de Magnus-Tetens.
        """
        b = 17.27
        c = 237.3
        alpha = ((b * temp_c) / (c + temp_c)) + math.log(max(rh, 1e-4) / 100.0)
        dp = (c * alpha) / (b - alpha)
        return round(dp, 2)

    @staticmethod
    def absolute_humidity(temp_c: float, rh: float) -> float:
        """
        Densidade de vapor de água (g/m³) derivada da equação dos gases ideais:
        AH = (216.7 * Ea) / (T_K) onde Ea é dada em hPa.
        """
        ea = AtmosphericPhysics.actual_vapor_pressure(temp_c, rh)
        t_k = temp_c + 273.15
        ah = (216.7 * ea) / t_k
        return round(ah, 3)

    @staticmethod
    def heat_index(temp_c: float, rh: float) -> float:
        """
        Cálculo do Índice de Calor / Sensação Térmica (NOAA / Rothfusz Regression).
        Converte para Fahrenheit internamente para aplicação dos coeficientes empíricos
        e retorna em Celsius.
        """
        t_f = temp_c * 1.8 + 32.0

        # Para condições amenas, a fórmula simples é suficiente
        hi_simple = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))
        if hi_simple < 80.0:
            return round((hi_simple - 32.0) / 1.8, 2)

        # Regressão de Rothfusz Completa
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

        # Ajuste de baixa umidade
        if rh < 13.0 and 80.0 <= t_f <= 112.0:
            adjustment = ((13.0 - rh) / 4.0) * math.sqrt((17.0 - abs(t_f - 95.0)) / 17.0)
            hi -= adjustment
        # Ajuste de alta umidade
        elif rh > 85.0 and 80.0 <= t_f <= 87.0:
            adjustment = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
            hi += adjustment

        return round((hi - 32.0) / 1.8, 2)

    @classmethod
    def compute_all(cls, temp_c: float, rh: float) -> dict:
        """
        Processa e retorna todas as métricas psicrométricas simultaneamente.
        """
        return {
            "temperatura": round(temp_c, 2),
            "umidade": round(rh, 2),
            "temperatura_kelvin": cls.kelvin(temp_c),
            "pressao_vapor_sat": cls.saturation_vapor_pressure(temp_c),
            "pressao_vapor_real": cls.actual_vapor_pressure(temp_c, rh),
            "ponto_orvalho": cls.dew_point(temp_c, rh),
            "umidade_absoluta": cls.absolute_humidity(temp_c, rh),
            "indice_calor": cls.heat_index(temp_c, rh)
        }