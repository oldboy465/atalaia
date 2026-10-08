from typing import Any, Dict, List
import requests
from datetime import datetime, timedelta
from app.config import Config
from app.services.physics_engine import AtmosphericPhysics

class ESPService:
    BASE_URL = "http://192.168.4.1"

    @classmethod
    def ping(cls) -> Dict[str, Any]:
        """
        Verifica a conectividade do ESP32 via rota /api/current com timeout curto.
        Evita bloquear as threads do Flask no Windows.
        """
        for host in Config.ESP32_HOSTS:
            target_url = f"http://{host}"
            try:
                resp = requests.get(f"{target_url}/api/current", timeout=Config.ESP32_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    data["online"] = True
                    data["active_url"] = target_url
                    cls.BASE_URL = target_url
                    return data
            except requests.RequestException:
                continue

        return {"online": False}

    @classmethod
    def extract_and_parse(cls) -> List[Dict[str, Any]]:
        """
        Descarrega todo o buffer Flash (LittleFS) do ESP32.
        Aplica sanitização rigorosa descartando ruídos de memória desalinhada
        e amostras de boot incompletas antes de gravar no banco.
        """
        ping_res = cls.ping()
        url = cls.BASE_URL if ping_res.get("online") else "http://192.168.4.1"

        try:
            resp = requests.get(f"{url}/api/export", timeout=12)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException:
            return []

        raw_items = payload.get("data", [])
        if not raw_items:
            return []

        now = datetime.now()

        # Agrupamento por ID de sessão física de boot
        sessions: Dict[int, List[Dict[str, Any]]] = {}
        for item in raw_items:
            sid = int(item.get("s", 1))
            if sid not in sessions:
                sessions[sid] = []
            sessions[sid].append(item)

        parsed: List[Dict[str, Any]] = []
        current_anchor_time = now

        for sid in sorted(sessions.keys(), reverse=True):
            session_records = sessions[sid]
            max_uptime = max(int(item.get("u", 0)) for item in session_records)

            for item in session_records:
                temp = float(item.get("t", 0.0))
                hum = float(item.get("h", 0.0))
                up = int(item.get("u", 0))
                mq_raw = int(item.get("mq", item.get("mq135_raw", 0)))

                # FILTROS DE INTEGRIDADE FÍSICA:
                # 1. ADC do ESP32 é de 12 bits (faixa válida estrita: 0 a 4095).
                # 2. Umidade não pode ser nula (evita Td em -105 °C).
                # 3. Temperatura deve estar na faixa operacional real do DHT22.
                if mq_raw > 4095 or mq_raw < 0:
                    continue
                if temp < 5.0 or temp > 65.0:
                    continue
                if hum < 10.0 or hum > 100.0:
                    continue

                delta_sec = max_uptime - up
                rec_time = current_anchor_time - timedelta(seconds=delta_sec)

                calc = AtmosphericPhysics.compute_all(temp, hum, mq_raw)
                calc["uptime_sec"] = up
                calc["session_id"] = sid
                calc["coletado_em"] = rec_time.strftime("%Y-%m-%d %H:%M:%S")
                parsed.append(calc)

            min_uptime = min(int(item.get("u", 0)) for item in session_records)
            session_duration_sec = max_uptime - min_uptime
            current_anchor_time = current_anchor_time - timedelta(seconds=session_duration_sec + 60)

        parsed.sort(key=lambda x: x["coletado_em"])
        return parsed

    @classmethod
    def clear_buffer(cls) -> bool:
        """Envia POST para resetar o buffer Flash no ESP32."""
        try:
            resp = requests.post(f"{cls.BASE_URL}/api/clear", timeout=2.5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    @classmethod
    def shutdown(cls) -> bool:
        """Envia comando de standby para suspender o sensor."""
        try:
            resp = requests.post(f"{cls.BASE_URL}/api/shutdown", timeout=2.5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    @classmethod
    def wakeup(cls) -> bool:
        """Envia pulso de ativação para o nó sensorial."""
        try:
            resp = requests.post(f"{cls.BASE_URL}/api/wakeup", timeout=2.5)
            return resp.status_code == 200
        except requests.RequestException:
            return False