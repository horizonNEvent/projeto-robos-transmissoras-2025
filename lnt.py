import requests
import os
import time
import logging
import json
import re
import pdfkit
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LNT_Robot")

# Configuração de Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'Data')
EMPRESAS_JSON_PATH = os.path.join(DATA_DIR, 'empresas.json')
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\TUST\LNT"

# Configuração wkhtmltopdf
WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'

def carregar_empresas():
    """Carrega os dados das empresas do arquivo JSON padrão"""
    try:
        if not os.path.exists(EMPRESAS_JSON_PATH):
            logger.error(f"Arquivo {EMPRESAS_JSON_PATH} não encontrado!")
            return {}
        with open(EMPRESAS_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar empresas: {e}")
        return {}

def obter_periodo_atual():
    """Retorna o período do mês anterior no formato AAAAMM (ex: 202412)"""
    hoje = datetime.now()
    mes_anterior = hoje.replace(day=1) - timedelta(days=1)
    return mes_anterior.strftime("%Y%m")

def sanitize_name(name):
    """Remove caracteres inválidos para Windows"""
    if not name: return "DESCONHECIDO"
    clean = re.sub(r'[<>:"/\\|?*]', '_', str(name))
    return " ".join(clean.split()).strip()

class LNTRobot:
    def __init__(self, empresa_nome, ons_code, ons_name):
        self.empresa_nome = empresa_nome
        self.ons_code = ons_code
        self.ons_name = ons_name
        self.session = requests.Session()
        self.base_url = "https://sys.sigetplus.com.br/cobranca"
        # Transmissor 1143 (LNT)
        self.url_faturas = f"{self.base_url}/transmitter/1143/invoices"
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # Padrão ASSU: TUST / LNT / Empresa / ONS
        self.output_path = os.path.join(BASE_DOWNLOAD_PATH, empresa_nome, str(ons_code))
        os.makedirs(self.output_path, exist_ok=True)

    def baixar_arquivo(self, url, filename, tipo):
        """Download de arquivo com tratamento para HTML (Boleto) e XML"""
        try:
            full_url = urljoin(self.base_url, url)
            res = self.session.get(full_url, headers=self.headers, timeout=30)
            
            if res.status_code == 200:
                content_type = res.headers.get('Content-Type', '').lower()
                
                # Se for Boleto em HTML, converter para PDF
                if 'text/html' in content_type and tipo == "BOLETO":
                    try:
                        config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
                        pdfkit.from_string(res.text, filename, configuration=config)
                        logger.info(f"    ✓ {tipo} convertido e salvo: {os.path.basename(filename)}")
                        return True
                    except Exception as e:
                        logger.error(f"    ❌ Erro ao converter HTML para PDF: {e}")
                
                # Download direto
                with open(filename, 'wb') as f:
                    f.write(res.content)
                logger.info(f"    ✓ {tipo} salvo: {os.path.basename(filename)}")
                return True
        except Exception as e:
            logger.error(f"    ❌ Erro ao baixar {tipo}: {e}")
        return False

    def processar(self, periodo):
        logger.info(f"\n>>> Processando {self.empresa_nome} | ONS {self.ons_code} ({self.ons_name})")
        
        params = {"agent": self.ons_code, "time": periodo}
        try:
            res = self.session.get(self.url_faturas, params=params, headers=self.headers)
            if res.status_code != 200:
                logger.error(f"    ❌ Erro ao acessar portal (Status {res.status_code})")
                return

            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select("table tbody tr")
            
            if not rows or "Nenhum registro" in rows[0].text:
                logger.info("    Nenhuma fatura encontrada para este período.")
                return

            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 5: continue
                
                # Nome da transmissora na linha (LNT pode ter variações ou info extra)
                trans_text = cols[0].get_text(strip=True)
                # Padronizar um pouco o nome para a pasta
                sigla_trans = sanitize_name(trans_text.split('-')[-1].strip() if '-' in trans_text else "LNT")
                
                # Pasta por ONS no padrão ASSU
                dest_dir = self.output_path
                
                num_nf = sanitize_name(cols[0].find('a').text.strip()) if cols[0].find('a') else "NF"
                timestamp = datetime.now().strftime("%Y%m%d")
                
                # XML e DANFE (geralmente na última coluna)
                links_col = cols[-1]
                xml_tag = links_col.find('a', string=re.compile(r'XML', re.I)) or links_col.find('a', attrs={"data-original-title": re.compile(r'XML', re.I)})
                danfe_tag = links_col.find('a', string=re.compile(r'DANFE|PDF', re.I)) or links_col.find('a', attrs={"data-original-title": re.compile(r'DANFE', re.I)})
                
                if xml_tag:
                    filename = os.path.join(dest_dir, f"XML_{self.ons_name}_{num_nf}_{timestamp}.xml")
                    self.baixar_arquivo(xml_tag['href'], filename, "XML")
                
                if danfe_tag:
                    filename = os.path.join(dest_dir, f"DANFE_{self.ons_name}_{num_nf}_{timestamp}.pdf")
                    self.baixar_arquivo(danfe_tag['href'], filename, "DANFE")

                # Boletos (Colunas 2, 3, 4 sugeridas no original)
                for i in range(1, 4):
                    boleto_tag = cols[i].find('a')
                    if boleto_tag and boleto_tag.get('href'):
                        filename = os.path.join(dest_dir, f"BOLETO_{self.ons_name}_{num_nf}_{i}_{timestamp}.pdf")
                        self.baixar_arquivo(boleto_tag['href'], filename, "BOLETO")

        except Exception as e:
            logger.error(f"    ❌ Erro fatal no processamento: {e}")

def main():
    logger.info("Iniciando Robô LNT (Luziania-Niquelandia Transmissora)")
    empresas_dict = carregar_empresas()
    if not empresas_dict: return

    # Baixar para o período atual (mês anterior)
    periodo = obter_periodo_atual()
    logger.info(f"Período alvo: {periodo}")

    for empresa_nome, ons_dict in empresas_dict.items():
        for ons_code, ons_name in ons_dict.items():
            robot = LNTRobot(empresa_nome, ons_code, ons_name)
            robot.processar(periodo)

if __name__ == "__main__":
    main()
    logger.info("\nProcesso finalizado!")