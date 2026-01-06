import requests
import os
import json
from datetime import datetime
import time
import urllib3
import argparse

# Desativa avisos de SSL inseguro (o site da Pantanal está com certificado expirado)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://www.pantanaltransmissao.com.br"
BASE_DIR_DOWNLOAD = r"C:\Users\Bruno\Downloads\TUST\PANTANAL"

# Carregar o arquivo empresas.json
with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Data/empresas.json'), 'r', encoding='utf-8') as f:
    EMPRESAS = json.load(f)

def baixar_titulo(empresa_nome, cod_ons, nome_ons):
    print(f"\nProcessando {empresa_nome} - ONS {cod_ons} - {nome_ons}")

    base_url = BASE_URL
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/xml,text/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': f'{base_url}/pantanal.html'
    }

    # Criar estrutura de pastas igual o da assu: BASE / empresa_nome / cod_ons
    base_path = os.path.join(BASE_DIR_DOWNLOAD, empresa_nome, cod_ons)
    os.makedirs(base_path, exist_ok=True)
    
    print(f"Baixando arquivo para {nome_ons} (Código ONS: {cod_ons})...")
    
    url = f"{base_url}/download.php"
    params = {
        'tswcode': cod_ons,
        'file': f'{cod_ons}.xml'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, verify=False)
        
        if response.status_code == 200:
            if len(response.content) < 100:
                 print(f"[ERROR] Arquivo muito pequeno/vazio para {nome_ons} (Tamanho: {len(response.content)} bytes). Possível erro no servidor.")
                 return False

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Padronizando nome do arquivo
            filename = f"NFe_{nome_ons}_{timestamp}.xml"
            filepath = os.path.join(base_path, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"[OK] XML baixado com sucesso: {filepath}")
            return True
        else:
            print(f"[ERROR] Erro ao baixar arquivo para {nome_ons}. Status code: {response.status_code}")
            print(f"Resposta do servidor: {response.text}")
            
    except Exception as e:
        print(f"[ERROR] Erro ao processar {nome_ons}: {e}")
    
    return False

def processar_todas_empresas():
    parser = argparse.ArgumentParser()
    parser.add_argument("--empresa", help="Nome da empresa para filtrar")
    parser.add_argument("--agente", help="Código ONS do agente para filtrar")
    args = parser.parse_args()

    for empresa_nome, cod_ons_dict in EMPRESAS.items():
        if args.empresa and args.empresa.strip().upper() != empresa_nome.strip().upper():
            continue
            
        print(f"\nProcessando empresa: {empresa_nome}")
        
        filtro_agentes = []
        if args.agente:
            filtro_agentes = [a.strip() for a in str(args.agente).split(',')]

        for cod_ons, nome_ons in cod_ons_dict.items():
            if filtro_agentes and str(cod_ons).strip() not in filtro_agentes:
                continue
                
            try:
                baixar_titulo(empresa_nome, str(cod_ons), nome_ons)
            except Exception as e:
                print(f"Erro ao processar {empresa_nome} - ONS {cod_ons} - {nome_ons}: {str(e)}")
            print("-" * 50)
            time.sleep(1)

if __name__ == "__main__":
    print("Iniciando download Pantanal...")
    print("=" * 50)
    processar_todas_empresas()
    print("\nProcesso finalizado!")
 