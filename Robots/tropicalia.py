import requests
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import argparse

# Configurações de Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'Data')
EMPRESAS_JSON_PATH = os.path.join(DATA_DIR, 'empresas.json')
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\TUST\TROPICALIA"

# URL da API
API_URL = "https://ms-site.cap-tropicalia.cust.app.br/site/usuaria"

# Headers da requisição
HEADERS = {
    "accept": "*/*",
    "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "origin": "https://nf-tropicalia-transmissora.cust.app.br",
    "referer": "https://nf-tropicalia-transmissora.cust.app.br/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

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

def download_file(url, filepath):
    """Baixa um arquivo da URL fornecida"""
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f"    [OK] Salvo: {os.path.basename(filepath)}")
            return True
        else:
            print(f"    [ERROR] Erro ao baixar (Status {response.status_code}): {os.path.basename(filepath)}")
    except Exception as e:
        print(f"    [ERROR] Erro no download: {e}")
    return False

def obter_competencia_alvo():
    """Determina a competência do mês anterior em português"""
    hoje = datetime.now()
    # Mês anterior
    primeiro_dia_mes_atual = hoje.replace(day=1)
    mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    
    meses_pt = {
        1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL",
        5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
        9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
    }
    
    return f"{meses_pt[mes_anterior.month]}-{mes_anterior.year}"

def processar_faturas(empresa_nome, ons_code, ons_name):
    """Busca e baixa as faturas para uma empresa/ONS específica"""
    print(f"\n>>> Processando {empresa_nome} | ONS {ons_code} ({ons_name})")
    
    # Caminho padrão ASSU: TUST / TROPICALIA / Empresa / ONS
    output_dir = os.path.join(BASE_DOWNLOAD_PATH, empresa_nome, ons_code)
    os.makedirs(output_dir, exist_ok=True)

    params = {"numeroOns": ons_code}
    try:
        response = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            print(f"    [ERROR] Erro na API (Status {response.status_code})")
            return False
            
        data = response.json()
        competencia_alvo = obter_competencia_alvo()
        found = False

        for item in data:
            # Limpar tags HTML do período (ex: <b>FEVEREIRO-2025</b>)
            periodo_raw = item.get('periodoContabil', '')
            periodo_limpo = BeautifulSoup(periodo_raw, 'html.parser').get_text().strip().upper()
            
            # Se for a competência alvo ou se quisermos baixar as recentes (aqui focamos na alvo)
            if periodo_limpo == competencia_alvo:
                found = True
                print(f"    Nota encontrada para {periodo_limpo}")
                
                # Nomes de arquivo padronizados
                base_name = f"{ons_name}_{periodo_limpo.replace('-', '_')}"
                
                # Download DANFE
                if item.get('linkDanfe'):
                    download_file(item['linkDanfe'], os.path.join(output_dir, f"DANFE_{base_name}.pdf"))
                
                # Download XML
                if item.get('linkXml'):
                    download_file(item['linkXml'], os.path.join(output_dir, f"XML_{base_name}.xml"))
                
                # Download Boleto
                if item.get('linkBoleto'):
                    download_file(item['linkBoleto'], os.path.join(output_dir, f"BOLETO_{base_name}.pdf"))
                
        if not found:
            print(f"    Aviso: Competência {competencia_alvo} não disponível para ONS {ons_code}")
            
    except Exception as e:
        print(f"    [ERROR] Erro ao processar faturas: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--empresa", help="Nome da empresa para filtrar")
    parser.add_argument("--agente", help="Código ONS do agente para filtrar")
    args = parser.parse_args()

    print("Iniciando Robô Tropicalia")
    empresas_dict = carregar_empresas()
    
    if not empresas_dict:
        print("Erro: Nenhuma empresa carregada.")
        return

    for empresa_nome, ons_dict in empresas_dict.items():
        if args.empresa and args.empresa.upper() != empresa_nome.upper():
            continue
            
        for ons_code, ons_name in ons_dict.items():
            if args.agente and str(args.agente) != str(ons_code):
                continue
                
            processar_faturas(empresa_nome, ons_code, ons_name)

if __name__ == "__main__":
    main()
    print("\nProcesso finalizado!")