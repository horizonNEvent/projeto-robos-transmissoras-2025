import requests
import os
import re
import time
import pdfkit
from datetime import datetime
from bs4 import BeautifulSoup

try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

class VereneRobot(BaseRobot):
    """
    Robô para Verene (via SigetPlus Company 41).
    URL: https://sys.sigetplus.com.br/cobranca/company/41/invoices
    Autenticação: Via query param ?agent=CODE.
    """

    def __init__(self):
        super().__init__("verene")
        self.base_url = "https://sys.sigetplus.com.br/cobranca/company/41/invoices"
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
        
        # Configuração PDF (Dinâmica via BaseRobot)
        self.pdf_config = self.get_pdf_config()

    def sanitize_filename(self, name):
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        return " ".join(name.split()).strip()

    def get_faturas_pagina(self, agent, time_period=None, page=1):
        try:
            params = {"agent": agent, "page": page}
            if time_period: params["time"] = time_period
            
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
            
            # Se boleto for HTML, converte
            content_type = r.headers.get('Content-Type', '').lower()
            if is_boleto and ('html' in content_type or not path.lower().endswith('.pdf')) and self.pdf_config:
                # Se a extensão for PDF mas content é HTML, pdfkit converte
                # Se for HTML puro, baixa e converte
                html_path = path + ".html"
                with open(html_path, 'wb') as f:
                    f.write(r.content)
                
                # Converte para o path final (PDF)
                # Garante que path termine em .pdf
                if not path.lower().endswith('.pdf'): path += ".pdf"
                
                pdfkit.from_file(html_path, path, configuration=self.pdf_config)
                try: os.remove(html_path) 
                except: pass
                self.logger.info(f"Boleto convertido: {os.path.basename(path)}")
            else:
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
                self.logger.info(f"Salvo: {os.path.basename(path)}")
                
        except Exception as e:
            self.logger.error(f"Erro download {os.path.basename(path)}: {e}")

    def run(self):
        agente_ons = self.args.agente
        if not agente_ons:
            self.logger.error("Agente ONS obrigatório (--agente).")
            return

        competencia_str = self.args.competencia
        # SigetPlus costuma aceitar YYYYMM ou YYYY-MM. Vamos passar YYYYMM.
        
        self.logger.info(f"Iniciando Verene para ONS {agente_ons} - Competência: {competencia_str or 'Mais Recente/Todos'}")
        
        base_path = self.get_output_path()
        out_dir = os.path.join(base_path, str(agente_ons))
        os.makedirs(out_dir, exist_ok=True)
        
        pagina = 1
        total_baixado = 0
        
        while True:
            html = self.get_faturas_pagina(agente_ons, competencia_str, pagina)
            if not html: break
            
            soup = BeautifulSoup(html, 'html.parser')
            linhas = soup.select('table tbody tr')
            
            # Se pagina vazia ou sem registros
            if not linhas or (len(linhas) == 1 and "Nenhum" in linhas[0].text):
                if pagina == 1: self.logger.warning("Nenhum registro encontrado.")
                break
            
            processed_in_page = 0
            for linha in linhas:
                cols = linha.find_all('td')
                if len(cols) < 5: continue
                
                transmissora = self.sanitize_filename(cols[0].text)
                num_nf = self.sanitize_filename(cols[1].text)
                
                t_dir = os.path.join(out_dir, transmissora)
                os.makedirs(t_dir, exist_ok=True)
                
                ts = datetime.now().strftime("%Y%m%d")
                nome_base = f"{agente_ons}_{num_nf}_{ts}"
                
                # XML
                xml_link = linha.select_one("a[data-original-title='XML']") or linha.find('a', string='XML')
                if xml_link:
                    url = f"https://sys.sigetplus.com.br{xml_link['href']}" if xml_link['href'].startswith('/') else xml_link['href']
                    self.baixar_arquivo(url, os.path.join(t_dir, f"XML_{nome_base}.xml"))
                
                # DANFE
                danfe_link = linha.select_one("a[data-original-title='DANFE']") or linha.find('a', string='DANFE')
                if danfe_link:
                    url = f"https://sys.sigetplus.com.br{danfe_link['href']}" if danfe_link['href'].startswith('/') else danfe_link['href']
                    self.baixar_arquivo(url, os.path.join(t_dir, f"DANFE_{nome_base}.pdf"))

                # Boletos (colunas variaveis, pegamos todos os links de boleto nas celulas 3, 4, 5)
                # O script original olhava colunas especificas. Vamos ser genericos: procurar links que contenham 'boleto' ou nao sejam XML/DANFE
                # Ou usar a logica original:
                boleto_links = linha.select("td:nth-child(4) a, td:nth-child(5) a, td:nth-child(6) a")
                for i, b_link in enumerate(boleto_links, 1):
                    if b_link.get('href'):
                         url = f"https://sys.sigetplus.com.br{b_link['href']}" if b_link['href'].startswith('/') else b_link['href']
                         self.baixar_arquivo(url, os.path.join(t_dir, f"BOLETO_{nome_base}_{i}.pdf"), is_boleto=True)

                processed_in_page += 1
                total_baixado += 1
            
            if processed_in_page == 0: break
            
            # Checar proxima pagina
            prox = soup.select('ul.pagination li a[rel="next"]')
            if not prox: break
            
            pagina += 1
            time.sleep(0.5)

        self.logger.info(f"Finalizado. Total baixado: {total_baixado}")

if __name__ == "__main__":
    robot = VereneRobot()
    robot.run()
