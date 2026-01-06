import requests
import json
from bs4 import BeautifulSoup
import os
import pdfkit
from datetime import datetime

# Configurações do Robô
TRANSMISSORA_ID = "1229"
TRANSMISSORA_NOME = "VINEYARDS"
BASE_PATH = rf'C:\Users\Bruno\Downloads\TUST\{TRANSMISSORA_NOME}'
WKHTML_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'

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
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}
    url = f'https://sys.sigetplus.com.br/cobranca/transmitter/{TRANSMISSORA_ID}/invoices?agent={agent_code}'
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200: return
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'class': 'table-striped'})
        if not table: return

        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 7: continue
            save_path = os.path.join(BASE_PATH, empresa_nome, agent_code)
            os.makedirs(save_path, exist_ok=True)
            
            # --- 1. XML ---
            xml_link = row.find('a', {'data-original-title': 'XML'})
            if xml_link:
                xml_name = xml_link['href'].split('/')[-1]
                res = requests.get(xml_link['href'])
                with open(os.path.join(save_path, xml_name), 'wb') as f: f.write(res.content)
                print(f"  [OK] XML: {xml_name}")

            # --- 2. DANFE ---
            danfe_link = row.find('a', {'data-original-title': 'DANFE'})
            if danfe_link:
                danfe_name = danfe_link['href'].split('/')[-1] + ".pdf"
                res = requests.get(danfe_link['href'])
                with open(os.path.join(save_path, danfe_name), 'wb') as f: f.write(res.content)
                print(f"  [OK] DANFE: {danfe_name}")

            # --- 3. BOLETOS (Conversão para PDF) ---
            for i in range(3, 6):
                b_link = cols[i].find('a')
                if b_link and 'billet' in b_link['href']:
                    b_url = b_link['href']
                    ts = datetime.now().strftime('%H%M%S')
                    pdf_name = f"Boleto_{agent_code}_{i}_{ts}.pdf"
                    html_name = f"Boleto_{agent_code}_{i}_{ts}.html"
                    
                    res_b = requests.get(b_url)
                    try:
                        # Tenta converter para PDF usando configuração otimizada para Windows
                        config = pdfkit.configuration(wkhtmltopdf=WKHTML_PATH)
                        options = {
                            'page-size': 'A4',
                            'encoding': 'UTF-8',
                            'quiet': '',
                            'no-outline': None,
                            'disable-smart-shrinking': None
                        }
                        pdfkit.from_string(res_b.text, os.path.join(save_path, pdf_name), configuration=config, options=options)
                        print(f"  [OK] BOLETO (PDF): {pdf_name}")
                    except Exception as pdf_err:
                        # Se falhar o PDF, salva o HTML como backup (garante que nada é perdido)
                        with open(os.path.join(save_path, html_name), 'wb') as f: f.write(res_b.content)
                        print(f"  [WARN] Falha PDF ({pdf_err}), salvo como HTML: {html_name}")
                        
    except Exception as e: print(f"Erro geral: {e}")

def main():
    empresas = carregar_empresas()
    for empresa_nome, mapping in empresas.items():
        for cod_ons, nome_ons in mapping.items():
            process_agent(str(cod_ons), nome_ons, empresa_nome)

if __name__ == "__main__":
    main()
