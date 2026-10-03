from typing import Any, Dict, List
import requests
from datetime import datetime, timedelta
from app.config import Config
from app.services.physics_engine import AtmosphericPhysics

class ESPService:
    BASE_URL = "http://192.168.4.1"

    @classmethod
    def ping(cls) -> Dict[str, Any]:
        try:
            resp = requests.get(f"{cls.BASE_URL}/api/current", timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                data["online"] = True
                data["active_url"] = cls.BASE_URL
                return data
        except requests.RequestException:
            pass
        return {"online": False}

    @classmethod
    def extract_and_parse(cls) -> List[Dict[str, Any]]:
        resp = requests.get(f"{cls.BASE_URL}/api/export", timeout=12)
        resp.raise_for_status()
        payload = resp.json()
        raw_items = payload.get("data", [])
        if not raw_items:
            return []

        now = datetime.now()

        # Agrupamento por sessão física de boot para preservar o tempo desligado
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
            max_uptime = max(item["u"] for item in session_records)

            for item in session_records:
                temp = float(item["t"])
                hum = float(item["h"])
                up = int(item["u"])
                
                delta_sec = max_uptime - up
                rec_time = current_anchor_time - timedelta(seconds=delta_sec)

                calc = AtmosphericPhysics.compute_all(temp, hum)
                calc["uptime_sec"] = up
                calc["coletado_em"] = rec_time.strftime("%Y-%m-%d %H:%M:%S")
                parsed.append(calc)

            min_uptime = min(item["u"] for item in session_records)
            session_duration_sec = max_uptime - min_uptime
            current_anchor_time = current_anchor_time - timedelta(seconds=session_duration_sec + 60)

        parsed.sort(key=lambda x: x["coletado_em"])
        return parsed

    @classmethod
    def clear_buffer(cls) -> bool:
        try:
            resp = requests.post(f"{cls.BASE_URL}/api/clear", timeout=2.0)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    @classmethod
    def shutdown(cls) -> bool:
        try:
            resp = requests.post(f"{cls.BASE_URL}/api/shutdown", timeout=2.0)
            return resp.status_code == 200
        except requests.RequestException:
            return False