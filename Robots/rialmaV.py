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

class RialmaVRobot(BaseRobot):
    
    def __init__(self):
        super().__init__("rialmav")

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
        # Lógica de Data (Mês Anterior)
        # Se competencia for passada via args, usa ela. Senão logica original (-1 mes)
        if self.args.competencia:
            c = self.args.competencia
            # Tratamento robusto para formatos YYYYMM, MM/YYYY e YYYY-MM
            if "/" in c: # MM/YYYY
                try:
                    m, y = c.split("/")
                    time_param = f"{y}{m.zfill(2)}"
                except: time_param = c.replace("/", "")
            elif "-" in c: # YYYY-MM ou MM-YYYY
                parts = c.split("-")
                if len(parts[0]) == 4: # YYYY-MM
                    time_param = f"{parts[0]}{parts[1]}"
                else: # MM-YYYY
                    time_param = f"{parts[1]}{parts[0]}"
            else:
                time_param = c # YYYYMM
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
                
                # Pasta Final: output_dir/Transmissora_AgentCode para garantir separação
                nome_pasta = f"{transmissora}_{agent}"
                final_dir = os.path.join(output_dir, nome_pasta)
                
                # Garante que a pasta da transmissora existe
                os.makedirs(final_dir, exist_ok=True)
                
                # Links
                boletos_links = [a["href"] for a in colunas[3].find_all("a")]
                nfe_links = [a["href"] for a in colunas[6].find_all("a")]

                # Resolve Links Finais
                xml_finais, danfe_finais = [], []
                for link in nfe_links:
                    self._resolve_siget_link(link, xml_finais, danfe_finais, session)

                # Boleto
                for idx, b_url in enumerate(boletos_links, 1):
                    # Salva na raiz do agente
                    path = os.path.join(final_dir, f"boleto_{numero}_{idx}.pdf")
                    try:
                        r = session.get(b_url)
                        self.html_para_pdf(r.text, path)
                    except Exception as e:
                        self.logger.error(f"Erro boleto {b_url}: {e}")

                # XMLs
                for x_url in xml_finais:
                    # Salva na raiz do agente
                    path = os.path.join(final_dir, os.path.basename(x_url))
                    self.baixar_arquivo(x_url, path, session=session)

                # DANFEs
                for d_url in danfe_finais:
                    # Salva na raiz do agente
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

    def run(self):
        self.logger.info("Iniciando RialmaV (SigetPlus)...")
        
        # CNPJ nao é usado, apenas Agente ONS
        # No front, user passa o Agente ONS no campo 'agente' ou 'user'
        if not self.args.agente:
            self.logger.error("Código ONS (--agente) é obrigatório.")
            return

        agentes_raw = str(self.args.agente).strip()
        lista_agentes = [a.strip() for a in agentes_raw.split(',') if a.strip()]
        
        base_dir = self.get_output_path()

        for agente_ons in lista_agentes:
            self.logger.info(f"--- Iniciando processamento para Agente: {agente_ons} ---")
            
            # Tenta SIGET
            self.processar_siget(agente_ons, base_dir)
            
        
        self.logger.info("Execução finalizada.")

if __name__ == "__main__":
    robot = RialmaVRobot()
    robot.run()
