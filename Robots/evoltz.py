import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime
import time
import pdfkit
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuração do PDFKit (wkhtmltopdf)
WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
PDFKIT_CONFIG = None
if os.path.exists(WKHTMLTOPDF_PATH):
    PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

def carregar_empresas():
    """Lê ../Data/empresas.json"""
    try:
        json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Data', 'empresas.json'))
        if not os.path.exists(json_path):
            logging.error(f"[EVOLTZ] Arquivo não encontrado: {json_path}")
            return {}
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"[EVOLTZ] Erro ao carregar empresas: {e}")
        return {}

class EvoltzRobot:
    def __init__(self, empresa_mae, cod_ons, nome_ons):
        self.session = requests.Session()
        self.base_url = "https://www2.nbte.com.br"
        self.empresa_mae = empresa_mae
        self.cod_ons = cod_ons
        self.nome_ons = nome_ons
        self.download_root = r"C:\Users\Bruno\Downloads\TUST\EVOLTZ"
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

    def login(self):
        logging.info(f"  [LOGIN] Iniciando login para {self.nome_ons} ({self.cod_ons})...")
        try:
            # GET inicial para cookies
            self.session.get(self.base_url, headers=self.headers)
            
            # POST Login (Logica do C#)
            payload = f"cod-ons-login={self.cod_ons}&AcaoClick=doLogin&idChave="
            response = self.session.post(self.base_url, data=payload, headers=self.headers)
            
            if "Painel de Fatura" in response.text or "Sair" in response.text:
                logging.info(f"  [OK] Login bem-sucedido.")
                return True
            else:
                logging.warning(f"  [FAIL] Falha no login para {self.cod_ons}.")
                return False
        except Exception as e:
            logging.error(f"  [ERROR] Erro no login: {e}")
            return False

    def get_faturas(self):
        try:
            response = self.session.get(self.base_url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Detecta competência (primeira opção do select filtro_mesano)
            filtro_mesano = ""
            select = soup.find('select', {'name': 'filtro_mesano'})
            if select and select.find('option'):
                option = select.find('option')
                filtro_mesano = option.get('value', '')
                logging.info(f"  [INFO] Competência detectada: {option.text.strip()}")
            
            table = soup.find('table', {'id': '_dataTable'}) or soup.find('table')
            if not table:
                logging.warning("  [WARN] Tabela de faturas não encontrada.")
                return [], ""
            
            faturas = []
            rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')[1:]
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 6:
                    transmissora = cols[0].text.strip()
                    # Links estão no formato callAcaoClick('Acao', 'Target', 'IdChave')
                    links = {
                        'fatura': self.extract_id(cols[1].find('a')),
                        'boleto': self.extract_id(cols[3].find('a')),
                        'danfe': self.extract_id(cols[4].find('a')),
                        'xml': self.extract_id(cols[5].find('a'), xml=True)
                    }
                    num_fatura = cols[1].text.strip()
                    
                    faturas.append({
                        'transmissora': transmissora,
                        'numero': num_fatura,
                        'links': links
                    })
            
            return faturas, filtro_mesano
        except Exception as e:
            logging.error(f"  [ERROR] Erro ao listar faturas: {e}")
            return [], ""

    def extract_id(self, a_tag, xml=False):
        if not a_tag: return None
        html = str(a_tag)
        # Regex para pegar o último parâmetro do callAcaoClick
        match = re.search(r"callAcaoClick\('.*?','.*?','(\d+)'\)", html)
        if match:
            return match.group(1)
        return None

    def baixar_documento(self, acao, id_chave, filtro_mesano, nome_arquivo, pasta_transmissora):
        caminho_final = os.path.join(pasta_transmissora, nome_arquivo)
        
        # Se for PDF/XML e já existe, pula
        if os.path.exists(caminho_final):
            return
        # Se for HTML que vira PDF e o PDF já existe, pula
        if nome_arquivo.endswith('.html') and os.path.exists(caminho_final.replace('.html', '.pdf')):
            return

        payload = {
            'filtro_mesano': filtro_mesano,
            'AcaoClick': acao,
            'idChave': id_chave,
            'id': ''
        }
        
        try:
            response = self.session.post(self.base_url, data=payload, headers=self.headers)
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '').lower()
                
                # XML ou PDF direto
                if 'xml' in content_type or 'pdf' in content_type or nome_arquivo.endswith('.xml'):
                    with open(caminho_final, 'wb') as f:
                        f.write(response.content)
                    logging.info(f"    [OK] Baixado: {nome_arquivo}")
                
                # HTML para converter em PDF (Boleto / Fatura)
                elif 'html' in content_type:
                    if PDFKIT_CONFIG:
                        pdf_path = caminho_final.replace('.html', '.pdf')
                        # Corrige encoding e base URL
                        html_content = response.text.replace('<head>', f'<head><base href="{self.base_url}/">')
                        # Alguns sites antigos usam ISO-8859-1
                        try:
                            pdfkit.from_string(html_content, pdf_path, configuration=PDFKIT_CONFIG, options={'quiet': '', 'encoding': 'UTF-8'})
                            logging.info(f"    [OK] PDF Gerado: {os.path.basename(pdf_path)}")
                        except:
                            # Se falhar PDF, salva HTML como fallback
                            with open(caminho_final, 'w', encoding='utf-8') as f:
                                f.write(html_content)
                    else:
                        with open(caminho_final, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        logging.info(f"    [OK] HTML Salvo: {nome_arquivo}")
        except Exception as e:
            logging.error(f"    [ERR] Erro ao baixar {nome_arquivo}: {e}")

def main():
    empresas = carregar_empresas()
    if not empresas: return

    # Período para pasta
    periodo_pasta = datetime.now().strftime("%Y%m")

    for grupo, mapping in empresas.items():
        logging.info(f"=== Processando Grupo: {grupo} ===")
        for cod_ons, nome_ons in mapping.items():
            robot = EvoltzRobot(grupo, cod_ons, nome_ons)
            if robot.login():
                faturas, comp = robot.get_faturas()
                if not faturas:
                    logging.info(f"  Nenhuma fatura encontrada para {nome_ons}.")
                    continue
                
                logging.info(f"  Encontradas {len(faturas)} faturas.")
                for fat in faturas:
                    t_nome = fat['transmissora']
                    num = fat['numero']
                    links = fat['links']
                    
                    # Pasta: EVOLTZ / Grupo / CodONS / Transmissora / Periodo
                    # Limpa nome da transmissora para pasta
                    t_pasta = re.sub(r'[^\w\s-]', '', t_nome).strip().replace(' ', '_')
                    path_dest = os.path.join(robot.download_root, grupo, cod_ons, t_pasta, periodo_pasta)
                    os.makedirs(path_dest, exist_ok=True)
                    
                    logging.info(f"    > {t_nome} (Fatura {num})")
                    
                    # Downloads baseados nas ações do C#
                    if links['fatura']:
                        robot.baixar_documento('Imprimir.fatura', links['fatura'], comp, f"Fatura_{num}.html", path_dest)
                    
                    if links['boleto']:
                        robot.baixar_documento('Imprimir.boleto', links['boleto'], comp, f"Boleto_{num}.html", path_dest)
                    
                    if links['danfe']:
                        robot.baixar_documento('Imprimir.danfe', links['danfe'], comp, f"DANFE_{num}.pdf", path_dest)
                    
                    if links['xml']:
                        robot.baixar_documento('Exportar.xml', links['xml'], comp, f"XML_{num}.xml", path_dest)

if __name__ == "__main__":
    main()
