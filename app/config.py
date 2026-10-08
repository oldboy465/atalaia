import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'atalaia_master_secret_key_82506920')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True') == 'True'

    # Caminho do banco de dados SQLite local
    DB_PATH = os.path.join(BASE_DIR, 'atalaia.db')

    # Alvos de rede do ESP32:
    # 1. IP direto do Ponto de Acesso em PRIMEIRO lugar (evita timeout de 3s do mDNS no Windows)
    # 2. Resolução por nome mDNS secundária
    ESP32_HOSTS = ['192.168.4.1', 'atalaia.local']
    ESP32_TIMEOUT = float(os.environ.get('ESP32_TIMEOUT', 1.2))