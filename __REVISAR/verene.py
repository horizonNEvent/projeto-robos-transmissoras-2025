import requests
from bs4 import BeautifulSoup
import os
import json
import re
import pdfkit
from datetime import datetime
from urllib.parse import urljoin

# Configurações de Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'Data')
EMPRESAS_JSON_PATH = os.path.join(DATA_DIR, 'empresas.json')
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\TUST\VERENE"

# Caminho do wkhtmltopdf para conversão de Boletos HTML
WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'

def sanitize_name(name):
    """Remove caracteres inválidos para Windows"""
    if not name: return "DESCONHECIDO"
    clean = re.sub(r'[<>:"/\\|?*]', '_', str(name))
    return " ".join(clean.split()).strip()

def carregar_empresas():
    """Carrega empresas do arquivo JSON padrão"""
    try:
        if not os.path.exists(EMPRESAS_JSON_PATH):
            print(f"Erro: Arquivo {EMPRESAS_JSON_PATH} não encontrado!")
            return {}
        with open(EMPRESAS_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar empresas: {e}")
        return {}

class VereneDownloader:
    def __init__(self, empresa_nome, ons_code, ons_name):
        self.empresa_nome = empresa_nome
        self.ons_code = ons_code
        self.ons_name = ons_name
        
        # Padrão ASSU: TUST / SISTEMA / Empresa / ONS
        self.base_path = os.path.join(BASE_DOWNLOAD_PATH, empresa_nome, str(ons_code))
        os.makedirs(self.base_path, exist_ok=True)
        
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }
        
    def download_pdf_from_html(self, url, dest_path):
        """Converte Boleto HTML em PDF usando wkhtmltopdf"""
        try:
            res = self.session.get(url, headers=self.headers)
            if res.status_code == 200:
                config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
                options = {
                    'page-size': 'A4',
                    'encoding': 'UTF-8',
                    'enable-local-file-access': True
                }
                pdfkit.from_string(res.text, dest_path, options=options, configuration=config)
                print(f"    ✓ BOLETO salvo: {os.path.basename(dest_path)}")
                return True
        except Exception as e:
            print(f"    ❌ Erro ao converter boleto para PDF: {e}")
        return False

    def download_direct(self, url, dest_path, tipo):
        """Download direto de XML ou PDF (DANFE)"""
        try:
            res = self.session.get(url, headers=headers if 'headers' in locals() else self.headers)
            if res.status_code == 200:
                with open(dest_path, 'wb') as f:
                    f.write(res.content)
                print(f"    ✓ {tipo} salvo: {os.path.basename(dest_path)}")
                return True
        except Exception as e:
            print(f"    ❌ Erro ao baixar {tipo}: {e}")
        return False

    def processar(self):
        print(f"\n>>> Processando {self.empresa_nome} | ONS {self.ons_code} ({self.ons_name})")
        
        # URL do SigetPlus para a Verene (Company ID 41)
        url = f"https://sys.sigetplus.com.br/cobranca/company/41/invoices?agent={self.ons_code}"
        
        try:
            res = self.session.get(url, headers=self.headers)
            if res.status_code != 200:
                print(f"    ❌ Erro ao acessar portal (Status {res.status_code})")
                return

            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select("table tbody tr")
            
            if not rows or "Nenhum registro" in rows[0].text:
                print(f"    Aviso: Nenhuma fatura encontrada no portal.")
                return

            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 5: continue
                
                # Info da Transmissora
                trans_text = cols[0].get_text(strip=True)
                trans_name = sanitize_name(trans_text.split('-')[1].strip() if '-' in trans_text else trans_text)
                
                # Criar subpasta para a transmissora (Padrão para portais multi-transmissora)
                trans_path = os.path.join(self.base_path, trans_name)
                os.makedirs(trans_path, exist_ok=True)
                
                num_nf = cols[1].get_text(strip=True)
                data_timestamp = datetime.now().strftime("%Y%m%d")
                
                # 1. Download XML e DANFE
                xml_link = row.select_one("a[data-original-title='XML']")
                danfe_link = row.select_one("a[data-original-title='DANFE']")
                
                if xml_link:
                    xml_url = urljoin(url, xml_link['href'])
                    self.download_direct(xml_url, os.path.join(trans_path, f"XML_{self.ons_name}_{num_nf}_{data_timestamp}.xml"), "XML")
                
                if danfe_link:
                    danfe_url = urljoin(url, danfe_link['href'])
                    self.download_direct(danfe_url, os.path.join(trans_path, f"DANFE_{self.ons_name}_{num_nf}_{data_timestamp}.pdf"), "DANFE")

                # 2. Download Boletos (Podem ser múltiplos colunas 3, 4, 5...)
                boleto_links = row.select("td:nth-child(4) a, td:nth-child(5) a, td:nth-child(6) a")
                for i, b_link in enumerate(boleto_links, 1):
                    if b_link.get('href'):
                        b_url = urljoin(url, b_link['href'])
                        b_filename = f"BOLETO_{self.ons_name}_{num_nf}_{i}_{data_timestamp}.pdf"
                        self.download_pdf_from_html(b_url, os.path.join(trans_path, b_filename))

        except Exception as e:
            print(f"    ❌ Erro fatal no processamento: {e}")

def main():
    print("Iniciando Robô Verene (SigetPlus)")
    empresas_dict = carregar_empresas()
    
    if not empresas_dict:
        return

    for empresa_nome, ons_dict in empresas_dict.items():
        for ons_code, ons_name in ons_dict.items():
            downloader = VereneDownloader(empresa_nome, ons_code, ons_name)
            downloader.processar()

if __name__ == "__main__":
    main()
    print("\nProcesso finalizado!")