import os
import logging
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import json
import sys
import pdfkit
import tempfile

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuração de diretórios
BASE_DIR_DOWNLOAD = r"C:\Users\Bruno\Downloads\TUST\ARTEON"

def carregar_empresas():
    """Carrega as informações das empresas do arquivo Data/empresas.json"""
    try:
        arquivo_json = os.path.join(os.path.dirname(__file__), 'Data', 'empresas.json')
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar empresas: {str(e)}")
        return {}

class ArteonDownloader:
    def __init__(self, ons_code, empresa_nome, nome_ons):
        self.ons_code = ons_code
        self.empresa_nome = empresa_nome
        self.nome_ons = nome_ons
        
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        
        # Configuração do wkhtmltopdf
        self.wkhtmltopdf_path = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        self.pdf_options = {
            'page-size': 'A4',
            'encoding': 'UTF-8',
            'no-images': False,
            'enable-local-file-access': True
        }
        
        # Caminho base igual ao da ASSU
        self.base_path = os.path.join(BASE_DIR_DOWNLOAD, self.empresa_nome, self.ons_code)
        os.makedirs(self.base_path, exist_ok=True)

    def baixar_boleto(self, url, nome_transmissora, indice=1):
        try:
            logger.info(f"[{self.empresa_nome}] Baixando boleto de: {url}")
            response = self.session.get(url, headers=self.headers)
            if response.status_code == 200:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                nome_arquivo = f"Boleto_{nome_transmissora}_{timestamp}.pdf"
                if indice > 1:
                    nome_arquivo = f"Boleto_{nome_transmissora}_{timestamp}_{indice}.pdf"
                
                # Criar subpasta para a transmissora
                path_transmissora = os.path.join(self.base_path, nome_transmissora)
                os.makedirs(path_transmissora, exist_ok=True)
                
                dest_pdf = os.path.join(path_transmissora, nome_arquivo)

                # Arteon boletos são HTML, precisam de conversão
                with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as tf:
                    tf.write(response.text)
                    temp_html = tf.name

                try:
                    config = pdfkit.configuration(wkhtmltopdf=self.wkhtmltopdf_path)
                    pdfkit.from_file(temp_html, dest_pdf, options=self.pdf_options, configuration=config)
                finally:
                    if os.path.exists(temp_html):
                        os.remove(temp_html)

                if os.path.exists(dest_pdf):
                    logger.info(f"[{self.empresa_nome}] Boleto salvo em: {dest_pdf}")
                    return True
            return False
        except Exception as e:
            logger.error(f"[{self.empresa_nome}] Erro ao processar boleto: {str(e)}")
            return False

    def baixar_arquivo(self, url, nome_transmissora, tipo="arquivo"):
        try:
            logger.info(f"[{self.empresa_nome}] Baixando {tipo} de: {url}")
            response = self.session.get(url, headers=self.headers)
            if response.status_code == 200:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                if tipo.upper() == "XML":
                    nome_arquivo = f"NFe_{nome_transmissora}_{timestamp}.xml"
                elif tipo.upper() == "DANFE":
                    nome_arquivo = f"DANFE_{nome_transmissora}_{timestamp}.pdf"
                else:
                    nome_arquivo = f"{tipo}_{nome_transmissora}_{timestamp}"

                # Criar subpasta para a transmissora
                path_transmissora = os.path.join(self.base_path, nome_transmissora)
                os.makedirs(path_transmissora, exist_ok=True)

                dest_path = os.path.join(path_transmissora, nome_arquivo)
                with open(dest_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"[{self.empresa_nome}] {tipo.capitalize()} salvo em: {dest_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"[{self.empresa_nome}] Erro ao processar {tipo}: {str(e)}")
            return False

    def run(self):
        try:
            logger.info(f"\nProcessando {self.empresa_nome} - {self.ons_code} - {self.nome_ons}")
            url = f"https://sys.sigetplus.com.br/cobranca/company/40/invoices?agent={self.ons_code}"
            response = self.session.get(url, headers=self.headers)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                rows = soup.select("table tbody tr")
                
                for row in rows:
                    transmissora_info = row.select_one("td:nth-child(1)").text.strip()
                    # Nome amigável da transmissora para a subpasta e arquivo
                    nome_transmissora = transmissora_info.split('-')[-1].strip().replace(' ', '_')
                    
                    # Download dos boletos
                    boleto_links = row.select("td:nth-child(4) a, td:nth-child(5) a, td:nth-child(6) a")
                    for i, boleto_link in enumerate(boleto_links, 1):
                        if boleto_link.get('href'):
                            self.baixar_boleto(boleto_link['href'], nome_transmissora, i)
                    
                    # Download XML e DANFE
                    xml_link = row.select_one("a[data-original-title='XML']")
                    danfe_link = row.select_one("a[data-original-title='DANFE']")
                    
                    if xml_link:
                        self.baixar_arquivo(xml_link['href'], nome_transmissora, "XML")
                    
                    if danfe_link:
                        self.baixar_arquivo(danfe_link['href'], nome_transmissora, "DANFE")
            else:
                logger.error(f"[{self.empresa_nome}] Erro ao acessar URL: {response.status_code}")

        except Exception as e:
            logger.error(f"[{self.empresa_nome}] Erro durante a execução: {str(e)}")

def main():
    empresas = carregar_empresas()
    if not empresas:
        logger.error("Não foi possível carregar as informações das empresas.")
        return

    for empresa_nome, cod_ons_dict in empresas.items():
        logger.info(f"\n=== Processando empresa: {empresa_nome} ===")
        for cod_ons, nome_ons in cod_ons_dict.items():
            try:
                downloader = ArteonDownloader(str(cod_ons), empresa_nome, nome_ons)
                downloader.run()
            except Exception as e:
                logger.error(f"Erro ao processar {empresa_nome} - ONS {cod_ons}: {str(e)}")
    
    logger.info("Processamento concluído!")

if __name__ == "__main__":
    main()
