import requests
import os
import re
import time
import pdfkit
from datetime import datetime
from bs4 import BeautifulSoup

# Import BaseRobot
try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

class TaesaRobot(BaseRobot):
    """
    Robô para Taesa (via SigetPlus Co 30).
    URL: https://sys.sigetplus.com.br/cobranca/company/30/invoices
    Autenticação: Via query param ?agent=CODE.
    """

    def __init__(self):
        super().__init__("taesa")
        self.base_url = "https://sys.sigetplus.com.br/cobranca/company/30/invoices"
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1"
        }
        
        # Configuração PDF (Dinâmica via BaseRobot)
        self.pdf_config = self.get_pdf_config()

    def sanitize_filename(self, name):
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '', name)
        return cleaned.strip()

    def get_faturas_pagina(self, agent, time_period, page=1):
        try:
            params = {
                "agent": agent,
                "time": time_period,
                "page": page,
                "_": int(datetime.now().timestamp() * 1000)
            }
            resp = self.session.get(self.base_url, params=params, headers=self.headers)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            self.logger.error(f"Erro página {page}: {e}")
            return None

    def baixar_arquivo(self, url, path, is_boleto=False):
        try:
            r = self.session.get(url, headers=self.headers, stream=True)
            r.raise_for_status()
            
            # Se for boleto HTML, converte
            content_type = r.headers.get('Content-Type', '').lower()
            if is_boleto and 'html' in content_type and self.pdf_config:
                # Salva HTML, converte, deleta HTML
                html_path = path + ".html"
                with open(html_path, 'wb') as f:
                    f.write(r.content) # Sem chunk para pdfkit ler arquivo
                
                pdfkit.from_file(html_path, path, configuration=self.pdf_config)
                try: os.remove(html_path) 
                except: pass
                self.logger.info(f"Boleto convertido: {os.path.basename(path)}")
            else:
                # Download direto (PDF ou XML)
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
                self.logger.info(f"Salvo: {os.path.basename(path)}")
                
        except Exception as e:
            self.logger.error(f"Erro download {os.path.basename(path)}: {e}")

    def run(self):
        agente_ons_arg = self.args.agente
        if not agente_ons_arg:
            self.logger.error("Agente ONS obrigatório (--agente).")
            return

        # Split multiple agents if provided
        agentes_raw = str(agente_ons_arg).strip()
        lista_agentes = [a.strip() for a in agentes_raw.split(',') if a.strip()]

        competencia_str = self.args.competencia
        if not competencia_str:
            # Padrão original: Mês anterior
            now = datetime.now()
            m, y = (now.month-1, now.year) if now.month > 1 else (12, now.year-1)
            competencia_str = f"{y}{m:02d}"
            self.logger.info(f"Competência não informada. Usando mês anterior: {competencia_str}")
        
        base_path = self.get_output_path()

        for agente_ons in lista_agentes:
            self.logger.info(f"--- Processando Taesa (Co 30) - Agente: {agente_ons} - Competência: {competencia_str} ---")
            
            # Subdir do Agente
            out_dir = os.path.join(base_path, str(agente_ons))
            os.makedirs(out_dir, exist_ok=True)
            
            pagina = 1
            total_baixado_agente = 0
            
            while True:
                self.logger.info(f"Lendo página {pagina} para Agente {agente_ons}...")
                html = self.get_faturas_pagina(agente_ons, competencia_str, pagina)
                if not html: break
                
                soup = BeautifulSoup(html, 'html.parser')
                linhas = soup.select('table tbody tr')
                if not linhas: break # Sem dados
                
                faturas_na_pag = 0
                for linha in linhas:
                    cols = linha.find_all('td')
                    if len(cols) < 8: continue
                    
                    transmissora = self.sanitize_filename(cols[0].text)
                    num_fatura = self.sanitize_filename(cols[1].text)
                    
                    # Subpasta Transmissora
                    t_dir = os.path.join(out_dir, transmissora)
                    os.makedirs(t_dir, exist_ok=True)
                    
                    nome_base = f"{num_fatura}_{competencia_str}"
                    
                    # XML
                    xml_btn = cols[7].find('a', class_='btn-primary')
                    if xml_btn:
                        url = xml_btn['href']
                        self.baixar_arquivo(url, os.path.join(t_dir, f"{nome_base}.xml"))
                    
                    # DANFE
                    danfe_btn = cols[7].find('a', class_='btn-info')
                    if danfe_btn:
                        url = danfe_btn['href']
                        self.baixar_arquivo(url, os.path.join(t_dir, f"{nome_base}_DANFE.pdf"))
                    
                    # Boleto
                    if cols[4].find('a'):
                        url = cols[4].find('a')['href']
                        self.baixar_arquivo(url, os.path.join(t_dir, f"{nome_base}_BOLETO.pdf"), is_boleto=True)
                    
                    faturas_na_pag += 1
                    total_baixado_agente += 1
                
                if faturas_na_pag == 0: break
                
                # Verifica paginação
                prox = soup.select('ul.pagination li a[rel="next"]')
                if not prox: break
                
                pagina += 1
                time.sleep(1)
            
            self.logger.info(f"Finalizado Agente {agente_ons}. Total baixado: {total_baixado_agente}")


if __name__ == "__main__":
    robot = TaesaRobot()
    robot.run()
