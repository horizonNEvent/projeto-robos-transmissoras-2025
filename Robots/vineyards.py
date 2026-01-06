import requests
import json
from bs4 import BeautifulSoup
import os
from datetime import datetime

# Configurações do Robô
TRANSMISSORA_ID = "1229"
TRANSMISSORA_NOME = "VINEYARDS"
BASE_PATH = rf'C:\Users\Bruno\Downloads\TUST\{TRANSMISSORA_NOME}'

def carregar_empresas():
    try:
        arquivo_json = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Data', 'empresas.json')
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar empresas: {e}")
        return {}

def process_agent(agent_code, nome_ons, empresa_nome):
    print(f"\n>>> Processando {empresa_nome} - {nome_ons} (ONS: {agent_code})")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }
    
    url = f'https://sys.sigetplus.com.br/cobranca/transmitter/{TRANSMISSORA_ID}/invoices?agent={agent_code}'
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Erro ao acessar portal: {response.status_code}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'class': 'table-striped'})
        if not table:
            print("Nenhuma fatura encontrada.")
            return

        rows = table.find_all('tr')[1:] # Pula cabeçalho
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 7: continue
            
            # Pasta de destino
            save_path = os.path.join(BASE_PATH, empresa_nome, agent_code)
            os.makedirs(save_path, exist_ok=True)
            
            # 1. Download XML
            xml_link = row.find('a', {'data-original-title': 'XML'})
            if xml_link:
                xml_url = xml_link['href']
                xml_name = xml_url.split('/')[-1]
                res = requests.get(xml_url)
                with open(os.path.join(save_path, xml_name), 'wb') as f:
                    f.write(res.content)
                print(f"  [OK] XML: {xml_name}")

            # 2. Download DANFE
            danfe_link = row.find('a', {'data-original-title': 'DANFE'})
            if danfe_link:
                danfe_url = danfe_link['href']
                danfe_name = danfe_url.split('/')[-1] + ".pdf"
                res = requests.get(danfe_url)
                with open(os.path.join(save_path, danfe_name), 'wb') as f:
                    f.write(res.content)
                print(f"  [OK] DANFE: {danfe_name}")

            # 3. Download Boletos (Colunas 4, 5 e 6 - Índices 3, 4, 5)
            for i in range(3, 6):
                b_link = cols[i].find('a')
                if b_link and 'billet' in b_link['href']:
                    b_url = b_link['href']
                    # Como o boleto é HTML no portal BPO, baixamos o HTML puro (formato original)
                    # Isso evita o erro do wkhtmltopdf e permite que o usuário abra no navegador/imprima
                    b_name = f"Boleto_{agent_code}_{i}_{datetime.now().strftime('%H%M%S')}.html"
                    res = requests.get(b_url)
                    with open(os.path.join(save_path, b_name), 'wb') as f:
                        f.write(res.content)
                    print(f"  [OK] BOLETO (HTML): {b_name}")

    except Exception as e:
        print(f"Erro no processamento: {e}")

def main():
    empresas = carregar_empresas()
    for empresa_nome, mapping in empresas.items():
        for cod_ons, nome_ons in mapping.items():
            process_agent(str(cod_ons), nome_ons, empresa_nome)

if __name__ == "__main__":
    main()
