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

class RialmasRobot(BaseRobot):
    
    def __init__(self):
        super().__init__("rialmas")

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

    def html_para_pdf(self, conteudo_html, caminho_destino):
        try:
            os.makedirs(os.path.dirname(caminho_destino), exist_ok=True)
            if PDFKIT_CONFIG:
                pdfkit.from_string(conteudo_html, caminho_destino, configuration=PDFKIT_CONFIG)
                self.logger.info(f"PDF Gerado: {os.path.basename(caminho_destino)}")
            else:
                self.logger.warning("wkhtmltopdf não configurado. PDF não gerado.")
        except Exception as e:
            self.logger.error(f"Falha ao converter HTML para PDF: {e}")

    # --- SIGETPLUS Logic ---
    def processar_siget(self, agent, output_dir):
        BASE_URL = "https://sys.sigetplus.com.br/cobranca/company/27/invoices"
        
        # Lógica de Data (Mês Anterior)
        # Se competencia for passada via args, usa ela. Senão logica original (-1 mes)
        if self.args.competencia:
            time_param = self.args.competencia # YYYYMM
        else:
            now = datetime.now()
            # Logica original Rialma: Mês atual - 1
            if now.month == 1:
                mes = 12
                ano = now.year - 1
            else:
                mes = now.month - 1
                ano = now.year
            time_param = f"{ano}{mes:02d}"

        url = f"{BASE_URL}?agent={agent}&time={time_param}&page=1"
        self.logger.info(f"[SIGETPLUS] Consultando Agent {agent} (Ref: {time_param})...")

        session = requests.Session()
        session.headers.update(HEADERS_COMMON)

        try:
            response = session.get(url)
            soup = BeautifulSoup(response.text, "html.parser")
            tabela = soup.find("table", {"class": "table-striped"})
            
            if not tabela:
                self.logger.info(f"[SIGETPLUS] Tabela não encontrada ou vazia.")
                return 

            rows = tabela.find("tbody").find_all("tr")
            for linha in rows:
                colunas = linha.find_all("td")
                transmissora = self.sanitizar_nome(colunas[0].get_text(strip=True))
                numero = self.sanitizar_nome(colunas[1].get_text(strip=True))
                
                # Pasta Final: output_dir/Transmissora
                final_dir = os.path.join(output_dir, transmissora)
                
                # Links
                boletos_links = [a["href"] for a in colunas[3].find_all("a")]
                nfe_links = [a["href"] for a in colunas[6].find_all("a")]

                # Resolve Links Finais
                xml_finais, danfe_finais = [], []
                for link in nfe_links:
                    self._resolve_siget_link(link, xml_finais, danfe_finais, session)

                # Boleto
                for idx, b_url in enumerate(boletos_links, 1):
                    path = os.path.join(final_dir, f"boleto_{numero}_{idx}.pdf")
                    try:
                        r = session.get(b_url)
                        self.html_para_pdf(r.text, path)
                    except Exception as e:
                        self.logger.error(f"Erro boleto {b_url}: {e}")

                # XMLs
                for x_url in xml_finais:
                    path = os.path.join(final_dir, os.path.basename(x_url))
                    self.baixar_arquivo(x_url, path, session=session)

                # DANFEs
                for d_url in danfe_finais:
                    path = os.path.join(final_dir, os.path.basename(d_url))
                    self.baixar_arquivo(d_url, path, session=session)

        except Exception as e:
            self.logger.error(f"[SIGETPLUS] Erro agent {agent}: {e}")

    def _resolve_siget_link(self, link, xml_list, danfe_list, session):
        try:
            if link.endswith('/XML/'):
                r = session.get(link)
                s = BeautifulSoup(r.text, "html.parser")
                for a in s.find_all("a", href=True):
                    if a["href"].endswith(".xml"):
                        xml_list.append(urljoin(link, a["href"]))
            elif link.endswith('/DANFE/'):
                r = session.get(link)
                s = BeautifulSoup(r.text, "html.parser")
                for a in s.find_all("a", href=True):
                    if a["href"].endswith(".pdf"):
                        danfe_list.append(urljoin(link, a["href"]))
            elif link.endswith('.xml'):
                xml_list.append(link)
            elif link.endswith('.pdf'):
                danfe_list.append(link)
        except: pass

    # --- ALUPAR Logic ---
    def processar_alupar(self, agent, output_dir):
        LOGIN_URL = "https://faturas.alupar.com.br:8090/Fatura/Emissao/4"
        BASE_DOMAIN = "https://faturas.alupar.com.br:8090"
        
        self.logger.info(f"[ALUPAR] Tentando conexão Agent {agent}...")
        
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
                self.logger.warning(f"[ALUPAR] Login falhou ou retornou erro para {agent}.")
                return

            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table')
            if not table:
                self.logger.info(f"[ALUPAR] Nenhuma tabela encontrada.")
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
                # Se forçado via argumento
                c = self.args.competencia
                target_year = int(c[:4])
                target_month = int(c[4:6])
            else:
                # Default: a mais recente da tabela
                target_year = target_date.year
                target_month = target_date.month

            to_process = [f for f in faturas if f['dt'].year == target_year and f['dt'].month == target_month]
            self.logger.info(f"[ALUPAR] Processando {len(to_process)} documentos de {target_month}/{target_year}")

            for item in to_process:
                row = item['row']
                cols = row.find_all('td')
                cliente = self.sanitizar_nome(cols[3].text) if len(cols) > 3 else "Cliente"
                doc_num = self.sanitizar_nome(cols[5].text) if len(cols) > 5 else "000"
                
                cliente_dir = os.path.join(output_dir, cliente)
                
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
            self.logger.error(f"[ALUPAR] Erro {agent}: {e}")


    def run(self):
        self.logger.info("Iniciando Rialmas (SigetPlus + Alupar)...")
        
        # CNPJ nao é usado, apenas Agente ONS
        # No front, user passa o Agente ONS no campo 'agente' ou 'user'
        if not self.args.agente:
            self.logger.error("Código ONS (--agente) é obrigatório.")
            return

        agente_ons = str(self.args.agente).strip()
        base_dir = self.get_output_path()
        
        # Tenta SIGET
        self.processar_siget(agente_ons, base_dir)
        
        # Tenta ALUPAR
        self.processar_alupar(agente_ons, base_dir)
        
        self.logger.info("Execução finalizada.")

if __name__ == "__main__":
    robot = RialmasRobot()
    robot.run()
