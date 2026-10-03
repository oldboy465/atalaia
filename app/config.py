import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'atalaia_master_secret_key_82506920')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True') == 'True'

    # Caminho do banco de dados SQLite local
    DB_PATH = os.path.join(BASE_DIR, 'atalaia.db')

    # Alvos de rede do ESP32 (Ordem de prioridade de busca)
    # 1. mDNS na rede residencial de casa
    # 2. IP gateway direto do Ponto de Acesso
    ESP32_HOSTS = ['atalaia.local', '192.168.4.1']
    ESP32_TIMEOUT = int(os.environ.get('ESP32_TIMEOUT', 3))