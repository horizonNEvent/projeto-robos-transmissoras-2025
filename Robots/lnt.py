import os
import requests
import json
import pdfkit
import tempfile
from bs4 import BeautifulSoup
from datetime import datetime
from base_robot import BaseRobot

class LNTRobot(BaseRobot):
    """
    Robô para a transmissora LNT (Luziania-Niquelandia Transmissora)
    Transmissor ID: 1143 no SigetPlus Cobrança
    """
    def __init__(self):
        super().__init__("lnt")
        self.base_url = "https://sys.sigetplus.com.br/cobranca/transmitter/1143/invoices"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        
        # Configuração do wkhtmltopdf usando a BaseRobot
        self.pdf_config = self.get_pdf_config()

    def carregar_referencia_empresas(self):
        """Carrega Data/empresas.json"""
        try:
            json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Data', 'empresas.json')
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Erro ao carregar empresas.json: {e}")
            return {}

    def get_period_str(self):
        """Define a competência (YYYYMM)."""
        if self.args.competencia:
            c = self.args.competencia.replace('/', '').replace('-', '')
            if len(c) == 6:
                return c
        
        # Padrão: Mês passado
        now = datetime.now()
        if now.month == 1:
            mes = 12
            ano = now.year - 1
        else:
            mes = now.month - 1
            ano = now.year
        return f"{ano}{mes:02d}"

    def get_invoices(self, agent_code, period):
        """Faz o scraping das faturas no portal de cobrança da LNT."""
        try:
            url = f"{self.base_url}?agent={agent_code}"
            if period:
                url += f"&time={period}"
            
            self.logger.info(f"Acessando: {url}")
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', {'class': 'table-striped'})
            if not table:
                return []
                
            rows = table.find_all('tr')[1:]
            data = []
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 5: continue # LNT tem pelo menos 5 colunas baseadas no esqueleto
                
                # Fatura Numero (pode estar na Col 0 ou 1 dependendo da variação)
                # No esqueleto lnt.py estava na Col 0
                fatura_el = cols[0].find('a')
                fatura_num = fatura_el.text.strip() if fatura_el else "NF"
                
                # Boletos nas colunas intermediárias (1, 2, 3)
                boletos = []
                for i in range(1, 4):
                    if i < len(cols):
                        b_el = cols[i].find('a')
                        if b_el and b_el.get('href'):
                            boletos.append({'data': b_el.text.strip(), 'link': b_el['href']})
                
                # XML e DANFE na última coluna
                xml_link = None
                danfe_link = None
                links_col = cols[-1].find_all('a')
                for link in links_col:
                    txt = (link.text or link.get('data-original-title', '') or "").upper()
                    if 'XML' in txt: xml_link = link['href']
                    elif 'DANFE' in txt or 'PDF' in txt: danfe_link = link['href']
                
                data.append({
                    'fatura_numero': fatura_num,
                    'boletos': boletos,
                    'xml_link': xml_link,
                    'danfe_link': danfe_link
                })
                
            return data

        except Exception as e:
            self.logger.error(f"Erro ao buscar faturas: {e}")
            return []

    def download_file(self, url, dest_path):
        try:
            if not url.startswith('http'):
                url = os.path.join("https://sys.sigetplus.com.br", url.lstrip('/'))
            
            r = requests.get(url, headers=self.headers, timeout=30)
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                f.write(r.content)
            return True
        except Exception as e:
            self.logger.error(f"Erro download {os.path.basename(dest_path)}: {e}")
            return False

    def convert_boleto(self, url, dest_path_pdf):
        """Baixa HTML e converte para PDF."""
        try:
            if not url.startswith('http'):
                url = os.path.join("https://sys.sigetplus.com.br", url.lstrip('/'))
                
            r = requests.get(url, headers=self.headers, timeout=30)
            r.raise_for_status()
            
            if self.pdf_config:
                try:
                    pdfkit.from_string(r.text, dest_path_pdf, configuration=self.pdf_config, options={'quiet': '', 'encoding': 'utf-8'})
                    return True
                except Exception as e:
                    self.logger.warning(f"Erro wkhtmltopdf: {e}")
            
            # Fallback: Salva HTML
            html_path = dest_path_pdf.replace('.pdf', '.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(r.text)
            self.logger.warning(f"Salvo como HTML: {os.path.basename(html_path)}")
            return True

        except Exception as e:
            self.logger.error(f"Erro processando boleto: {e}")
            return False

    def run(self):
        period = self.get_period_str()
        empresas = self.carregar_referencia_empresas()
        
        target_empresa = self.args.empresa
        target_agents = self.get_agents()
        
        base_output_dir = self.get_output_path()
        self.logger.info(f"Iniciando Robô LNT - Competência: {period}")

        total_files = 0

        for emp_nome, mapping in empresas.items():
            if target_empresa and target_empresa.upper() != emp_nome.upper():
                continue
            
            for ons_code, agent_name in mapping.items():
                ons_str = str(ons_code)
                if target_agents and ons_str not in target_agents:
                    continue
                
                self.logger.info(f"Processando {emp_nome} - {agent_name} ({ons_str})...")
                
                invoices = self.get_invoices(ons_str, period)
                
                if not invoices:
                    self.logger.info(f"  Nenhuma fatura encontrada para {ons_str} em {period}.")
                    continue
                
                agent_dir = os.path.join(base_output_dir, emp_nome, ons_str)
                os.makedirs(agent_dir, exist_ok=True)
                
                for inv in invoices:
                    f_num = inv['fatura_numero']
                    
                    # XML
                    if inv['xml_link']:
                        xml_path = os.path.join(agent_dir, f"XML_{agent_name}_{f_num}.xml")
                        if self.download_file(inv['xml_link'], xml_path):
                            total_files += 1
                            self.logger.info(f"    [OK] XML: {f_num}")
                            
                    # DANFE
                    if inv['danfe_link']:
                        danfe_path = os.path.join(agent_dir, f"DANFE_{agent_name}_{f_num}.pdf")
                        if self.download_file(inv['danfe_link'], danfe_path):
                            total_files += 1
                            self.logger.info(f"    [OK] DANFE: {f_num}")
                            
                    # Boletos
                    for i, bol in enumerate(inv['boletos']):
                        if bol['link']:
                            ts = datetime.now().strftime("%H%M%S")
                            bol_path = os.path.join(agent_dir, f"BOLETO_{agent_name}_{f_num}_{i+1}_{ts}.pdf")
                            if self.convert_boleto(bol['link'], bol_path):
                                total_files += 1
                                self.logger.info(f"    [OK] BOLETO {i+1}")

        self.logger.info(f"Finalizado. {total_files} arquivos baixados.")

if __name__ == "__main__":
    bot = LNTRobot()
    bot.run()
