import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
import json
import logging
import pdfkit
import tempfile

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuração de diretórios
TRANSMISSORA_ID = "1229"
TRANSMISSORA_NOME = "VINEYARDS"
BASE_DIR_DOWNLOAD = rf"C:\Users\Bruno\Downloads\TUST\{TRANSMISSORA_NOME}"

def carregar_empresas():
    try:
        arquivo_json = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Data', 'empresas.json')
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar empresas: {str(e)}")
        return {}

class SigetBPORobot:
    def __init__(self, ons_code, empresa_nome, nome_ons):
        self.ons_code = ons_code
        self.empresa_nome = empresa_nome
        self.nome_ons = nome_ons
        
        self.base_url = f"https://sys.sigetplus.com.br/cobranca/transmitter/{TRANSMISSORA_ID}/invoices"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        self.config_pdf = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
        self.base_path = os.path.join(BASE_DIR_DOWNLOAD, self.empresa_nome, self.ons_code)
        os.makedirs(self.base_path, exist_ok=True)

    def get_invoices(self):
        try:
            url = f"{self.base_url}?agent={self.ons_code}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', {'class': 'table-striped'})
            if not table: return pd.DataFrame()
            
            rows = table.find_all('tr')[1:]
            data = []
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 7:
                    agent_info = cols[0].text.strip()
                    nome_transmissora_row = agent_info.split('-')[-1].strip().replace(' ', '_')
                    fatura_numero = cols[1].find('a').text.strip() if cols[1].find('a') else ""
                    boletos = [c.find('a')['href'] for c in cols[3:6] if c.find('a')]
                    
                    xml_link = None
                    danfe_link = None
                    for link in cols[6].find_all('a'):
                        title = link.get('data-original-title', '').upper()
                        if 'XML' in title: xml_link = link['href']
                        elif 'DANFE' in title: danfe_link = link['href']
                    
                    data.append({
                        'nome_transmissora': nome_transmissora_row,
                        'fatura_numero': fatura_numero,
                        'boletos': boletos,
                        'xml_link': xml_link,
                        'danfe_link': danfe_link
                    })
            return pd.DataFrame(data)
        except Exception as e:
            logger.error(f"Erro ao buscar faturas: {e}")
            return pd.DataFrame()

    def baixar_boleto(self, url, nome_transmissora, indice=1):
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                timestamp = datetime.now().strftime('%Y%m%d')
                nome_arquivo = f"Boleto_{nome_transmissora}_{timestamp}_{indice}.pdf"
                dest_dir = os.path.join(self.base_path, nome_transmissora)
                os.makedirs(dest_dir, exist_ok=True)
                dest_path = os.path.join(dest_dir, nome_arquivo)
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as tf:
                    tf.write(response.text)
                    temp_html = tf.name
                try:
                    pdfkit.from_file(temp_html, dest_path, configuration=self.config_pdf, options={'javascript-delay': 1000})
                finally:
                    if os.path.exists(temp_html): os.remove(temp_html)
                return True
        except Exception as e:
            logger.error(f"Erro no boleto: {e}")
        return False

    def baixar_arquivo(self, url, nome_transmissora, tipo):
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                timestamp = datetime.now().strftime('%Y%m%d')
                ext = ".xml" if tipo.upper() == "XML" else ".pdf"
                nome_arquivo = f"{tipo.upper()}_{nome_transmissora}_{timestamp}{ext}"
                dest_dir = os.path.join(self.base_path, nome_transmissora)
                os.makedirs(dest_dir, exist_ok=True)
                with open(os.path.join(dest_dir, nome_arquivo), 'wb') as f:
                    f.write(response.content)
                return True
        except Exception as e:
            logger.error(f"Erro no {tipo}: {e}")
        return False

    def run(self):
        df = self.get_invoices()
        if df.empty: return
        for _, row in df.iterrows():
            for i, link in enumerate(row['boletos'], 1): self.baixar_boleto(link, row['nome_transmissora'], i)
            if row['xml_link']: self.baixar_arquivo(row['xml_link'], row['nome_transmissora'], "XML")
            if row['danfe_link']: self.baixar_arquivo(row['danfe_link'], row['nome_transmissora'], "DANFE")

def main():
    empresas = carregar_empresas()
    for empresa_nome, ons_dict in empresas.items():
        for ons_code, nome_ons in ons_dict.items():
            robot = SigetBPORobot(str(ons_code), empresa_nome, nome_ons)
            robot.run()

if __name__ == "__main__":
    main()
