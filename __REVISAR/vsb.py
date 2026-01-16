import requests
import os
import zipfile
from datetime import datetime, timedelta
import json
import concurrent.futures

# Configurações de Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'Data')
EMPRESAS_JSON_PATH = os.path.join(DATA_DIR, 'empresas.json')
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\TUST\VSB"

def carregar_empresas():
    """Carrega os dados das empresas do arquivo JSON padrão"""
    try:
        if not os.path.exists(EMPRESAS_JSON_PATH):
            print(f"Erro: Arquivo {EMPRESAS_JSON_PATH} não encontrado!")
            return {}
        with open(EMPRESAS_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar empresas: {e}")
        return {}

def baixar_arquivo(codigo, data, folder_path):
    """Obtém a URL do ZIP e solicita o download"""
    url = f"https://www.vsbtrans.com.br/getFiles.php?codigo={codigo}&data={data}"
    headers = {
        "accept": "*/*",
        "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "referer": "https://www.vsbtrans.com.br/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            json_response = response.json()
            zip_url = json_response.get("zipUrl")
            if zip_url:
                download_url = f"https://www.vsbtrans.com.br{zip_url}"
                return download_and_extract_zip(download_url, codigo, data, folder_path)
            else:
                print(f"    [ONS {codigo}] Erro: 'zipUrl' não encontrado no JSON.")
        else:
            print(f"    [ONS {codigo}] Erro API: Status {response.status_code}")
    except Exception as e:
        print(f"    [ONS {codigo}] Erro na requisição: {e}")
    return False

def download_and_extract_zip(download_url, codigo, data, folder_path):
    """Baixa o ZIP e extrai diretamente na pasta da ONS"""
    try:
        response = requests.get(download_url, timeout=60)
        if response.status_code == 200:
            zip_filename = f"TEMP_{codigo}_{data}.zip"
            zip_path = os.path.join(folder_path, zip_filename)
            
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            # Extrair arquivos
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(folder_path)
            
            # Remover ZIP temporário
            os.remove(zip_path)
            print(f"    ✓ Arquivos extraídos com sucesso em: {folder_path}")
            return True
        else:
            print(f"    [ONS {codigo}] Falha ao baixar ZIP: Status {response.status_code}")
    except Exception as e:
        print(f"    [ONS {codigo}] Erro no download/extração: {e}")
    return False

def obter_data_alvo():
    """Calcula o mês anterior no formato YYYY.MM (Padrão VSB)"""
    hoje = datetime.now()
    mes_anterior = hoje.replace(day=1) - timedelta(days=1)
    return mes_anterior.strftime("%Y.%m")

def processar_ons(empresa_nome, cod_ons, nome_ons, data_alvo):
    print(f"\n>>> Processando {empresa_nome} | ONS {cod_ons} ({nome_ons})")
    
    # Caminho Padrão: TUST / VSB / Empresa / ONS
    ons_folder = os.path.join(BASE_DOWNLOAD_PATH, empresa_nome, cod_ons)
    os.makedirs(ons_folder, exist_ok=True)
    
    baixar_arquivo(cod_ons, data_alvo, ons_folder)

def main():
    print("Iniciando Robô VSB (Vila do Conde / Santa Bárbara)")
    empresas_dict = carregar_empresas()
    if not empresas_dict:
        return

    data_alvo = obter_data_alvo()
    print(f"Competência alvo: {data_alvo}")

    # Processamento sequencial (ou paralelo se preferir)
    for empresa_nome, ons_dict in empresas_dict.items():
        for cod_ons, nome_ons in ons_dict.items():
            processar_ons(empresa_nome, cod_ons, nome_ons, data_alvo)

if __name__ == '__main__':
    main()
    print("\nProcesso finalizado!")