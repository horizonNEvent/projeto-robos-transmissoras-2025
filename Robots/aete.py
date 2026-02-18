import os
import json
import re
import time
import requests
import pdfkit
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

# Import BaseRobot
try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

# Configuração do PDFKit (wkhtmltopdf)
WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
PDFKIT_CONFIG = None
if os.path.exists(WKHTMLTOPDF_PATH):
    PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

HEADERS_COMMON = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
}

class AETERobot(BaseRobot):
    
    def __init__(self):
        super().__init__("aete")

    def sanitizar_nome(self, nome):
        """Remove caracteres inválidos e normaliza espaços."""
        nome_limpo = re.sub(r'[<>:"/\\|?*\n\r]', ' ', nome)
        nome_limpo = re.sub(r'\s+', ' ', nome_limpo).strip()
        return nome_limpo

    def baixar_arquivo(self, url, caminho_destino, session=None):
        try:
            if session:
                resp = session.get(url, headers=HEADERS_COMMON)
            else:
                resp = requests.get(url, headers=HEADERS_COMMON)
            resp.raise_for_status()
            
            # Garante que o diretório existe
            os.makedirs(os.path.dirname(caminho_destino), exist_ok=True)
            
            with open(caminho_destino, 'wb') as f:
                f.write(resp.content)
            self.logger.info(f"Salvo: {os.path.basename(caminho_destino)}")
        except Exception as e:
            self.logger.error(f"Falha ao baixar {url}: {e}")

    # --- ALUPAR / AETE Logic ---
    def processar_alupar(self, agent, output_dir):
        # AETE -> Portal Alupar
        LOGIN_URL = "https://faturas.alupar.com.br:8090/Fatura/Emissao/49"
        BASE_DOMAIN = "https://faturas.alupar.com.br:8090"
        
        self.logger.info(f"[ALUPAR-AETE] Tentando conexão Agent {agent}...")
        
        session = requests.Session()
        session.cookies.set('cmplz_banner-status', 'dismissed', domain='stnordeste.com.br')
        
        headers = {
            'User-Agent': HEADERS_COMMON['User-Agent'],
            'Referer': 'https://stnordeste.com.br/',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': BASE_DOMAIN,
            'Upgrade-Insecure-Requests': '1',
        }
        
        payload = {
            'Codigo': agent, # Código ONS
            'btnEntrar': 'OK',
            '__RequestVerificationToken': ''
        }
        
        try:
            resp = session.post(LOGIN_URL, data=payload, headers=headers)
            if resp.status_code != 200 or "erro" in resp.text.lower():
                self.logger.warning(f"[ALUPAR-AETE] Login falhou ou retornou erro para {agent}.")
                return

            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table')
            if not table:
                self.logger.info(f"[ALUPAR-AETE] Nenhuma tabela encontrada.")
                return

            rows = table.find_all('tr')[1:]
            
            # Coleta Faturas de interesse
            faturas = []
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 7: continue 
                
                try:
                    dt_obj = datetime.strptime(cols[6].text.strip(), "%d/%m/%Y")
                    faturas.append({'row': row, 'dt': dt_obj})
                except: continue
            
            if not faturas: return

            # Filtra mês de interesse
            faturas.sort(key=lambda x: x['dt'], reverse=True)
            target_date = faturas[0]['dt'] # Mais recente por padrão
            
            if self.args.competencia:
                c = self.args.competencia
                # Tratamento robusto para formatos YYYYMM, MM/YYYY e YYYY-MM
                if "/" in c: # MM/YYYY
                    try:
                        m, y = c.split("/")
                        target_year = int(y)
                        target_month = int(m)
                    except: 
                        target_year = target_date.year
                        target_month = target_date.month
                elif "-" in c: # YYYY-MM ou MM-YYYY
                    parts = c.split("-")
                    if len(parts[0]) == 4: # YYYY-MM
                        target_year = int(parts[0])
                        target_month = int(parts[1])
                    else: # MM-YYYY
                        target_year = int(parts[1])
                        target_month = int(parts[0])
                else: # YYYYMM
                     try:
                        target_year = int(c[:4])
                        target_month = int(c[4:6])
                     except:
                        target_year = target_date.year
                        target_month = target_date.month
            else:
                # Default: a mais recente da tabela
                target_year = target_date.year
                target_month = target_date.month

            to_process = [f for f in faturas if f['dt'].year == target_year and f['dt'].month == target_month]
            self.logger.info(f"[ALUPAR-AETE] Processando {len(to_process)} documentos de {target_month}/{target_year}")

            for item in to_process:
                row = item['row']
                cols = row.find_all('td')
                cliente = self.sanitizar_nome(cols[3].text) if len(cols) > 3 else "Cliente"
                doc_num = self.sanitizar_nome(cols[5].text) if len(cols) > 5 else "000"
                
                cliente_dir = os.path.join(output_dir, cliente)
                os.makedirs(cliente_dir, exist_ok=True)
                
                links = row.find_all('a', href=True)
                for link in links:
                    onclick = link.get('onclick', '')
                    title = link.get('title', '')
                    target_url = None
                    
                    if 'window.open' in onclick:
                        try:
                            part = onclick.split("'")[1]
                            if part.startswith('/'):
                                target_url = BASE_DOMAIN + part
                        except: pass
                    
                    if target_url:
                        ts = datetime.now().strftime('%Y%m%d')
                        if 'Visualizar NF' in title: name = f"NF_{doc_num}_{ts}.pdf"
                        elif 'Baixar XML' in title: name = f"XML_{doc_num}_{ts}.xml"
                        elif 'Baixar DANFE' in title: name = f"DANFE_{doc_num}_{ts}.pdf"
                        else: name = f"Doc_{doc_num}_{ts}.bin"
                            
                        self.baixar_arquivo(target_url, os.path.join(cliente_dir, name), session=session)

        except Exception as e:
            self.logger.error(f"[ALUPAR-AETE] Erro {agent}: {e}")

    def run(self):
        self.logger.info("Iniciando AETE (Alupar)...")
        
        # CNPJ nao é usado, apenas Agente ONS
        if not self.args.agente:
            self.logger.error("Código ONS (--agente) é obrigatório.")
            return

        agentes_raw = str(self.args.agente).strip()
        lista_agentes = [a.strip() for a in agentes_raw.split(',') if a.strip()]
        
        base_dir = self.get_output_path()

        for agente_ons in lista_agentes:
            self.logger.info(f"--- Iniciando processamento para Agente: {agente_ons} ---")
            
            # Tenta Lógica Alupar (AETE)
            self.processar_alupar(agente_ons, base_dir)
        
        self.logger.info("Execução finalizada.")

if __name__ == "__main__":
    robot = AETERobot()
    robot.run()
