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
        Verifica a conectividade do ESP32 via rota de telemetria instantânea (/api/current).
        Retorna dicionário contendo o estado online, métricas e leituras brutas de gás.
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
        Descarrega todo o buffer em anel gravado na memória Flash (LittleFS) do ESP32.
        Desserializa temperatura, umidade, tempo ativo, sessão e o valor do MQ-135 ('mq').
        Submete cada tupla sensorial ao AtmosphericPhysics.compute_all com física de gases.
        """
        # Garante que usamos a URL ativa verificada
        ping_res = cls.ping()
        url = cls.BASE_URL if ping_res.get("online") else "http://192.168.4.1"

        resp = requests.get(f"{url}/api/export", timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        raw_items = payload.get("data", [])
        if not raw_items:
            return []

        now = datetime.now()

        # Agrupamento estruturado por ID de sessão de boot físico para preservar descontinuidades
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
            max_uptime = max(int(item["u"]) for item in session_records)

            for item in session_records:
                temp = float(item["t"])
                hum = float(item["h"])
                up = int(item["u"])
                mq_raw = int(item.get("mq", item.get("mq135_raw", 0)))

                delta_sec = max_uptime - up
                rec_time = current_anchor_time - timedelta(seconds=delta_sec)

                # Processamento higrotérmico e de química de gases simultâneo
                calc = AtmosphericPhysics.compute_all(temp, hum, mq_raw)
                calc["uptime_sec"] = up
                calc["session_id"] = sid
                calc["coletado_em"] = rec_time.strftime("%Y-%m-%d %H:%M:%S")
                parsed.append(calc)

            min_uptime = min(int(item["u"]) for item in session_records)
            session_duration_sec = max_uptime - min_uptime
            current_anchor_time = current_anchor_time - timedelta(seconds=session_duration_sec + 60)

        parsed.sort(key=lambda x: x["coletado_em"])
        return parsed

    @classmethod
    def clear_buffer(cls) -> bool:
        """Envia comando POST para limpar a partição Flash LittleFS do ESP32."""
        try:
            resp = requests.post(f"{cls.BASE_URL}/api/clear", timeout=3.0)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    @classmethod
    def shutdown(cls) -> bool:
        """Envia comando para colocar os sensores do nó em Standby de economia de bateria."""
        try:
            resp = requests.post(f"{cls.BASE_URL}/api/shutdown", timeout=3.0)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    @classmethod
    def wakeup(cls) -> bool:
        """Envia comando para reativar medições e LEDs do nó sensorial."""
        try:
            resp = requests.post(f"{cls.BASE_URL}/api/wakeup", timeout=3.0)
            return resp.status_code == 200
        except requests.RequestException:
            return False