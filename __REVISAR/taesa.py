import requests
from bs4 import BeautifulSoup
import os
import time
import logging
from datetime import datetime
import re
import json
import pdfkit

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("SigetPlusDownloader")

def sanitize_filename(name: str, max_length: int = 255) -> str:
    if not name:
        return ""
    cleaned = " ".join(str(name).split())
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '', cleaned)
    cleaned = cleaned.strip().strip('.')
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip()
    reserved = {"CON","PRN","AUX","NUL"} | {f"COM{i}" for i in range(1,10)} | {f"LPT{i}" for i in range(1,10)}
    if cleaned.upper() in reserved:
        cleaned = cleaned + "_"
    return cleaned

def carregar_empresas():
    """Carrega os dados das empresas do arquivo JSON"""
    arquivo_json = os.path.join(os.path.dirname(__file__), 'Data', 'empresas.json')
    try:
        if not os.path.exists(arquivo_json):
            logger.error(f"Arquivo {arquivo_json} não encontrado!")
            return {}
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar empresas: {e}")
        return {}

EMPRESAS = carregar_empresas()

class SigetPlusDownloader:
    def __init__(self, download_dir=r"C:\Users\Bruno\Downloads\TUST\TAESA", wkhtmltopdf_path=None):
        self.session = requests.Session()
        self.base_url = "https://sys.sigetplus.com.br/cobranca"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        self.wkhtmltopdf_path = wkhtmltopdf_path
        self.pdf_config = pdfkit.configuration(wkhtmltopdf=self.wkhtmltopdf_path) if self.wkhtmltopdf_path else None

    def acessar_site(self, agent, time_period, page=1):
        try:
            url = f"{self.base_url}/company/30/invoices"
            params = {"agent": agent, "time": time_period, "page": page, "_": int(datetime.now().timestamp() * 1000)}
            response = self.session.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Erro ao acessar site para agente {agent}: {e}")
            return None

    def extrair_links_faturas(self, html_content):
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            faturas = []
            linhas = soup.select('table tbody tr')
            for linha in linhas:
                colunas = linha.find_all('td')
                if len(colunas) < 8: continue
                links = {}
                if colunas[1].find('a'): links['fatura'] = colunas[1].find('a')['href']
                if colunas[4].find('a'): links['boleto'] = colunas[4].find('a')['href']
                xml_btn = colunas[7].find('a', class_='btn-primary')
                if xml_btn: links['xml'] = xml_btn['href']
                danfe_btn = colunas[7].find('a', class_='btn-info')
                if danfe_btn: links['danfe'] = danfe_btn['href']
                if links:
                    faturas.append({
                        'transmissora': sanitize_filename(colunas[0].text),
                        'numero_fatura': sanitize_filename(colunas[1].text, max_length=100),
                        'links': links
                    })
            return faturas
        except Exception as e:
            logger.error(f"Erro ao extrair links: {e}")
            return []

    def verificar_proxima_pagina(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        return len(soup.select('ul.pagination li a[rel="next"]')) > 0

    def baixar_arquivo(self, url, nome_arquivo, dir_path):
        try:
            response = self.session.get(url, headers=self.headers, stream=True)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '').lower()
            ext = ''
            if 'pdf' in content_type: ext = '.pdf'
            elif 'xml' in content_type: ext = '.xml'
            elif 'html' in content_type: ext = '.html'
            
            filepath = os.path.join(dir_path, f"{nome_arquivo}{ext}")
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
            
            if ext == '.html' and 'boleto' in nome_arquivo.lower() and self.pdf_config:
                pdf_path = os.path.join(dir_path, f"{nome_arquivo}.pdf")
                pdfkit.from_file(filepath, pdf_path, configuration=self.pdf_config)
                os.remove(filepath)
                return pdf_path
            return filepath
        except Exception as e:
            logger.error(f"Erro ao baixar {url}: {e}")
            return None

    def baixar_fatura(self, fatura, agent, time_period, empresa_nome):
        try:
            transmissora_full = fatura['transmissora']
            numero_fatura = fatura['numero_fatura']
            links = fatura['links']
            
            dir_ons = os.path.join(self.download_dir, empresa_nome, str(agent))
            os.makedirs(dir_ons, exist_ok=True)
            dir_transmissora = os.path.join(dir_ons, sanitize_filename(transmissora_full))
            os.makedirs(dir_transmissora, exist_ok=True)
            
            nome_base = f"{numero_fatura}_{time_period}"
            if 'xml' in links: self.baixar_arquivo(links['xml'], f"{nome_base}_XML", dir_transmissora)
            if 'danfe' in links: self.baixar_arquivo(links['danfe'], f"{nome_base}_DANFE", dir_transmissora)
            if 'boleto' in links: self.baixar_arquivo(links['boleto'], f"{nome_base}_BOLETO", dir_transmissora)
            return True
        except Exception as e:
            logger.error(f"Erro ao baixar fatura {fatura.get('numero_fatura')}: {e}")
            return False

    def baixar_faturas_periodo(self, agent, time_period, empresa_nome):
        try:
            pagina, total = 1, 0
            while True:
                html = self.acessar_site(agent, time_period, pagina)
                if not html: break
                faturas = self.extrair_links_faturas(html)
                if not faturas: break
                for f in faturas:
                    if self.baixar_fatura(f, agent, time_period, empresa_nome): total += 1
                    time.sleep(0.5)
                if not self.verificar_proxima_pagina(html): break
                pagina += 1
                time.sleep(1)
            return total
        except Exception as e:
            logger.error(f"Erro no período {time_period} para {agent}: {e}")
            return 0

if __name__ == "__main__":
    print("-" * 50)
    print("TAESA - SigetPlus Downloader")
    print("-" * 50)
    
    wkhtmltopdf_path = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    if not os.path.exists(wkhtmltopdf_path): wkhtmltopdf_path = None
    
    downloader = SigetPlusDownloader(wkhtmltopdf_path=wkhtmltopdf_path)
    
    # Mês anterior
    now = datetime.now()
    m, y = (now.month-1, now.year) if now.month > 1 else (12, now.year-1)
    periodo = f"{y}{m:02d}"
    
    total_geral = 0
    for empresa, mapping in EMPRESAS.items():
        print(f"\nEmpresa: {empresa}")
        for code, name in mapping.items():
            print(f"  > {name} ({code})")
            n = downloader.baixar_faturas_periodo(code, periodo, empresa)
            total_geral += n
            print(f"    Baixadas: {n}")
    
    print(f"\nTotal baixado: {total_geral}")
