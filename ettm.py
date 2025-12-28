import requests
import json
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Configurações de Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'Data')
EMPRESAS_JSON_PATH = os.path.join(DATA_DIR, 'empresas.json')
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\TUST\ETTM"

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

def sanitize_name(name):
    """Remove caracteres inválidos para Windows"""
    if not name: return "DESCONHECIDO"
    clean = re.sub(r'[<>:"/\\|?*]', '_', str(name))
    return " ".join(clean.split()).strip()

class ETTMRobot:
    def __init__(self, empresa_nome, ons_code, ons_name):
        self.empresa_nome = empresa_nome
        self.ons_code = ons_code
        self.ons_name = ons_name
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }
        # Padrão ASSU: TUST / SISTEMA / Empresa / ONS
        self.output_path = os.path.join(BASE_DOWNLOAD_PATH, empresa_nome, str(ons_code))
        os.makedirs(self.output_path, exist_ok=True)

    def baixar_arquivo(self, url, filename, tipo):
        """Faz download de um documento (XML ou DANFE)"""
        try:
            full_url = urljoin("https://sys.sigetplus.com.br", url)
            res = self.session.get(full_url, headers=self.headers, timeout=30)
            if res.status_code == 200:
                with open(filename, 'wb') as f:
                    f.write(res.content)
                print(f"    ✓ {tipo} salvo: {os.path.basename(filename)}")
                return True
            else:
                print(f"    ❌ Erro ao baixar {tipo} (Status {res.status_code})")
        except Exception as e:
            print(f"    ❌ Erro no download de {tipo}: {e}")
        return False

    def processar(self):
        print(f"\n>>> Processando {self.empresa_nome} | ONS {self.ons_code} ({self.ons_name})")
        
        # Transmissor 1311 (ETTM)
        url = f"https://sys.sigetplus.com.br/cobranca/transmitter/1311/invoices?agent={self.ons_code}"
        
        try:
            res = self.session.get(url, headers=self.headers, timeout=30)
            if res.status_code != 200:
                print(f"    ❌ Erro ao acessar portal (Status {res.status_code})")
                return

            soup = BeautifulSoup(res.text, 'html.parser')
            # Busca links de XML e DANFE na tabela de faturas
            # O SigetPlus costuma usar data-original-title ou o texto do link
            xml_tag = soup.find('a', attrs={"data-original-title": re.compile(r'XML', re.I)}) or \
                      soup.find('a', string=re.compile(r'XML', re.I))
            
            danfe_tag = soup.find('a', attrs={"data-original-title": re.compile(r'DANFE|PDF', re.I)}) or \
                        soup.find('a', string=re.compile(r'DANFE|PDF', re.I))

            if xml_tag or danfe_tag:
                # Extrair número da fatura para o nome do arquivo
                invoice_link = soup.find('a', href=lambda x: x and 'invoices' in x)
                invoice_number = sanitize_name(invoice_link.get_text(strip=True)) if invoice_link else "NF"
                
                timestamp = datetime.now().strftime("%Y%m")
                
                if xml_tag:
                    xml_filename = os.path.join(self.output_path, f"XML_{self.ons_name}_{invoice_number}_{timestamp}.xml")
                    self.baixar_arquivo(xml_tag['href'], xml_filename, "XML")
                
                if danfe_tag:
                    danfe_filename = os.path.join(self.output_path, f"DANFE_{self.ons_name}_{invoice_number}_{timestamp}.pdf")
                    self.baixar_arquivo(danfe_tag['href'], danfe_filename, "DANFE")
            else:
                print(f"    Aviso: Nenhum documento encontrado para ONS {self.ons_code}")

        except Exception as e:
            print(f"    ❌ Erro fatal no processamento: {e}")

def main():
    print("Iniciando Robô ETTM (SigetPlus Transmissor 1311)")
    empresas_dict = carregar_empresas()
    if not empresas_dict:
        return

    for empresa_nome, ons_dict in empresas_dict.items():
        for ons_code, ons_name in ons_dict.items():
            robot = ETTMRobot(empresa_nome, ons_code, ons_name)
            robot.processar()

if __name__ == "__main__":
    main()
    print("\nProcesso finalizado!")