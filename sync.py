"""
Módulo de Sincronização e Reconstrução Temporal - Estação Atalaia
Reconstrução cronológica, associação de localidade e gravação transacional.
"""

from datetime import datetime, timedelta
import requests
from database import insert_batch_registros, log_sync_event
from statistics_engine import (
    calcular_ponto_orvalho, 
    calcular_sensacao_termica,
    calcular_pressao_vapor,
    calcular_umidade_absoluta,
    calcular_entalpia,
    calcular_indice_thom
)

ESP_BASE_URL = "http://192.168.4.1"
REQUEST_TIMEOUT = 12.0

def executar_sincronizacao(local_nome="Sede Principal"):
    """
    Executa a transferência segura com injeção do local físico designado.
    """
    local_nome = local_nome.strip() if local_nome and local_nome.strip() else "Sede Principal"
    resultado = {
        "sucesso": False,
        "registros_sincronizados": 0,
        "local": local_nome,
        "mensagem": ""
    }

    try:
        start_res = requests.post(f"{ESP_BASE_URL}/sync/start", timeout=REQUEST_TIMEOUT)
        if start_res.status_code != 200:
            resultado["mensagem"] = f"ESP32 recusou inicio de sincronizacao (HTTP {start_res.status_code})"
            log_sync_event(local_nome, 0, "FALHA", resultado["mensagem"])
            return resultado

        start_data = start_res.json()
        staging_count = start_data.get("staging_count", 0)
        last_sample_delta_ms = start_data.get("last_sample_delta_ms", 0)

        if staging_count == 0:
            resultado["sucesso"] = True
            resultado["mensagem"] = "ESP32 conectada, mas nao ha registros pendentes no buffer."
            log_sync_event(local_nome, 0, "INFO", resultado["mensagem"])
            return resultado

        pull_res = requests.get(f"{ESP_BASE_URL}/sync/pull", timeout=REQUEST_TIMEOUT)
        if pull_res.status_code != 200:
            requests.post(f"{ESP_BASE_URL}/sync/rollback", timeout=REQUEST_TIMEOUT)
            resultado["mensagem"] = "Falha ao descarregar buffer da ESP32. Rollback executado."
            log_sync_event(local_nome, 0, "FALHA", resultado["mensagem"])
            return resultado

        raw_csv = pull_res.text.strip()
        if not raw_csv:
            resultado["sucesso"] = True
            resultado["mensagem"] = "Buffer retornado vazio pela ESP32."
            return resultado

        linhas = [l.strip() for l in raw_csv.split('\n') if l.strip()]

        agora = datetime.now()
        tempo_ultimo_registro = agora - timedelta(milliseconds=last_sample_delta_ms)

        registros_preparados = []
        agora_iso = agora.strftime("%Y-%m-%d %H:%M:%S")

        parsed_amostras = []
        for linha in linhas:
            partes = linha.split(';')
            if len(partes) >= 4:
                seq = int(partes[0])
                temp = float(partes[1])
                hum = float(partes[2])
                intervalo_s = float(partes[3]) / 1000.0
                parsed_amostras.append((seq, temp, hum, intervalo_s))

        n_amostras = len(parsed_amostras)
        for idx, (seq, temp, hum, intervalo_s) in enumerate(parsed_amostras):
            segundos_atras = (n_amostras - 1 - idx) * intervalo_s
            timestamp_amostra = tempo_ultimo_registro - timedelta(seconds=segundos_atras)
            timestamp_str = timestamp_amostra.strftime("%Y-%m-%d %H:%M:%S")

            dp = calcular_ponto_orvalho(temp, hum)
            hi = calcular_sensacao_termica(temp, hum)
            e, _ = calcular_pressao_vapor(temp, hum)
            ah = calcular_umidade_absoluta(temp, hum)
            ent = calcular_entalpia(temp, hum)
            thom = calcular_indice_thom(temp, hum)

            registros_preparados.append((
                seq,
                timestamp_str,
                local_nome,
                temp,
                hum,
                dp,
                hi,
                e,
                ah,
                ent,
                thom,
                intervalo_s,
                "ESP32_ATALAIA",
                agora_iso
            ))

        linhas_gravadas = insert_batch_registros(registros_preparados)

        commit_res = requests.post(f"{ESP_BASE_URL}/sync/commit", timeout=REQUEST_TIMEOUT)
        if commit_res.status_code == 200:
            resultado["sucesso"] = True
            resultado["registros_sincronizados"] = linhas_gravadas
            resultado["mensagem"] = f"Sincronizacao bem-sucedida! {linhas_gravadas} registros integrados para o local '{local_nome}'."
            log_sync_event(local_nome, linhas_gravadas, "SUCESSO", resultado["mensagem"])
        else:
            resultado["mensagem"] = "Dados salvos no SQLite, mas o ESP32 falhou na confirmacao do commit."
            log_sync_event(local_nome, linhas_gravadas, "ALERTA", resultado["mensagem"])

    except requests.exceptions.RequestException as e:
        resultado["mensagem"] = f"Falha de comunicacao com a ESP32: {str(e)}"
        log_sync_event(local_nome, 0, "ERRO_CONEXAO", resultado["mensagem"])
    except Exception as ex:
        resultado["mensagem"] = f"Erro no processamento interno da sincronizacao: {str(ex)}"
        log_sync_event(local_nome, 0, "ERRO_INTERNO", resultado["mensagem"])

    return resultado

if __name__ == "__main__":
    print("==================================================")
    print(" ATALAIA - DIAGNOSTICO AUTONOMO DE SINCRONIZACAO  ")
    print("==================================================")
    loc = input("Informe o local do registro (ex: Laboratorio): ")
    res = executar_sincronizacao(loc)
    print(f"Sucesso: {res['sucesso']}")
    print(f"Registros Sincronizados: {res['registros_sincronizados']}")
    print(f"Local atribuido: {res['local']}")
    print(f"Mensagem: {res['mensagem']}")
    print("==================================================")