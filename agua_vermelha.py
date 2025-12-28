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
BASE_DIR_DOWNLOAD = r"C:\Users\Bruno\Downloads\TUST\AGUAVERMELHA"

def carregar_empresas():
    """Carrega as informações das empresas do arquivo Data/empresas.json"""
    try:
        arquivo_json = os.path.join(os.path.dirname(__file__), 'Data', 'empresas.json')
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar empresas: {str(e)}")
        return {}

class AguaVermelhaRobot:
    def __init__(self, ons_code, empresa_nome, nome_ons):
        self.ons_code = ons_code
        self.empresa_nome = empresa_nome
        self.nome_ons = nome_ons
        
        self.base_url = "https://sys.sigetplus.com.br/cobranca/transmitter/1327/invoices"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        self.config_pdf = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
        
        # Caminho base igual ao da ASSU
        self.base_path = os.path.join(BASE_DIR_DOWNLOAD, self.empresa_nome, self.ons_code)
        os.makedirs(self.base_path, exist_ok=True)

    def get_invoices(self, period=None):
        try:
            url = f"{self.base_url}?agent={self.ons_code}"
            if period:
                url = f"{url}&time={period}"
            
            logger.info(f"[{self.empresa_nome}] Acessando URL: {url}")
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', {'class': 'table-striped'})
            
            if not table:
                logger.warning(f"[{self.empresa_nome}] Nenhuma tabela encontrada para ONS {self.ons_code}")
                return pd.DataFrame()
            
            rows = table.find_all('tr')[1:]
            data = []
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 7:
                    agent_info = cols[0].text.strip()
                    nome_transmissora = agent_info.split('-')[-1].strip().replace(' ', '_')
                    
                    fatura_element = cols[1].find('a')
                    fatura_numero = fatura_element.text.strip() if fatura_element else ""
                    
                    boletos = []
                    for i in range(3, 6):
                        boleto_element = cols[i].find('a')
                        if boleto_element:
                            boletos.append(boleto_element['href'])
                    
                    xml_link = None
                    danfe_link = None
                    links = cols[6].find_all('a')
                    for link in links:
                        title = link.get('data-original-title', '').upper()
                        if 'XML' in title:
                            xml_link = link['href']
                        elif 'DANFE' in title:
                            danfe_link = link['href']
                    
                    data.append({
                        'nome_transmissora': nome_transmissora,
                        'fatura_numero': fatura_numero,
                        'boletos': boletos,
                        'xml_link': xml_link,
                        'danfe_link': danfe_link
                    })
            
            return pd.DataFrame(data)
            
        except Exception as e:
            logger.error(f"[{self.empresa_nome}] Erro ao buscar faturas: {e}")
            return pd.DataFrame()

    def baixar_boleto(self, url, nome_transmissora, indice=1):
        try:
            logger.info(f"[{self.empresa_nome}] Baixando boleto: {nome_transmissora}")
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                nome_arquivo = f"Boleto_{nome_transmissora}_{timestamp}.pdf"
                if indice > 1:
                    nome_arquivo = f"Boleto_{nome_transmissora}_{timestamp}_{indice}.pdf"
                
                path_transmissora = os.path.join(self.base_path, nome_transmissora)
                os.makedirs(path_transmissora, exist_ok=True)
                
                dest_path = os.path.join(path_transmissora, nome_arquivo)

                with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as tf:
                    tf.write(response.text)
                    temp_html = tf.name

                try:
                    options = {'page-size': 'A4', 'encoding': 'utf-8', 'javascript-delay': 1000}
                    pdfkit.from_file(temp_html, dest_path, options=options, configuration=self.config_pdf)
                finally:
                    if os.path.exists(temp_html): os.remove(temp_html)
                
                if os.path.exists(dest_path):
                    logger.info(f"[{self.empresa_nome}] Boleto salvo: {dest_path}")
                    return True
            return False
        except Exception as e:
            logger.error(f"[{self.empresa_nome}] Erro no boleto: {e}")
            return False

    def baixar_arquivo(self, url, nome_transmissora, tipo="arquivo"):
        try:
            logger.info(f"[{self.empresa_nome}] Baixando {tipo}: {nome_transmissora}")
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                ext = ".xml" if tipo.upper() == "XML" else ".pdf"
                nome_arquivo = f"{tipo.upper()}_{nome_transmissora}_{timestamp}{ext}"
                if tipo.upper() == "XML":
                    nome_arquivo = f"NFe_{nome_transmissora}_{timestamp}.xml"

                path_transmissora = os.path.join(self.base_path, nome_transmissora)
                os.makedirs(path_transmissora, exist_ok=True)

                dest_path = os.path.join(path_transmissora, nome_arquivo)
                with open(dest_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"[{self.empresa_nome}] {tipo.capitalize()} salvo: {dest_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"[{self.empresa_nome}] Erro no {tipo}: {e}")
            return False

    def run(self):
        logger.info(f"\nProcessando {self.empresa_nome} - {self.ons_code} - {self.nome_ons}")
        df = self.get_invoices()
        
        if df.empty:
            return
            
        for _, row in df.iterrows():
            # Boletos
            for i, link in enumerate(row['boletos'], 1):
                self.baixar_boleto(link, row['nome_transmissora'], i)
            
            # XML
            if row['xml_link']:
                self.baixar_arquivo(row['xml_link'], row['nome_transmissora'], "XML")
                
            # DANFE
            if row['danfe_link']:
                self.baixar_arquivo(row['danfe_link'], row['nome_transmissora'], "DANFE")

def main():
    empresas = carregar_empresas()
    if not empresas:
        logger.error("Empresas não carregadas.")
        return

    for empresa_nome, ons_dict in empresas.items():
        logger.info(f"\n=== Empresa: {empresa_nome} ===")
        for ons_code, nome_ons in ons_dict.items():
            try:
                robot = AguaVermelhaRobot(str(ons_code), empresa_nome, nome_ons)
                robot.run()
            except Exception as e:
                logger.error(f"Erro no processamento {empresa_nome}/{ons_code}: {e}")

if __name__ == "__main__":
    main()