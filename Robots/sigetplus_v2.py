import os
import requests
import json
import pdfkit
import re
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from base_robot import BaseRobot

class SigetPlusV2Robot(BaseRobot):
    """
    Robô SigetPlus V2 - Processa múltiplas transmissoras que seguem o padrão SigetPlus Cobrança.
    """
    def __init__(self):
        super().__init__("sigetplusv2")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        self.pdf_config = self.get_pdf_config()
        self.targets = self.carregar_targets()

    def carregar_targets(self):
        try:
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Data', 'sigetplus_v2_targets.json')
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Erro ao carregar alvos V2: {e}")
            return {}

    def get_period_str(self):
        if self.args.competencia:
            c = self.args.competencia.replace('/', '').replace('-', '')
            if len(c) == 6: return c
        
        now = datetime.now()
        # Padrão: Mês anterior
        if now.month == 1:
            mes, ano = 12, now.year - 1
        else:
            mes, ano = now.month - 1, now.year
        return f"{ano}{mes:02d}"

    def processar_transmissora(self, trans_id, trans_name, agent_code, period, emp_nome):
        url = f"https://sys.sigetplus.com.br/cobranca/transmitter/{trans_id}/invoices?agent={agent_code}"
        if period:
            url += f"&time={period}"
        
        self.logger.info(f"    Verificando Transmissora {trans_id} ({trans_name})...")
        try:
            res = requests.get(url, headers=self.headers, timeout=30)
            if res.status_code != 200:
                return
            
            soup = BeautifulSoup(res.text, 'html.parser')
            table = soup.find('table', {'class': 'table-striped'})
            if not table: return
            
            rows = table.find_all('tr')[1:]
            if not rows: return
            
            agent_dir = os.path.join(self.get_output_path(), emp_nome, agent_code, self.sanitize_folder_name(trans_name))
            os.makedirs(agent_dir, exist_ok=True)
            
            files_count = 0
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 5: continue
                
                # Fatura Numero
                fatura_el = cols[0].find('a')
                f_num = fatura_el.text.strip() if fatura_el else "NF"
                
                # XML e DANFE (geralmente última coluna)
                xml_link = None
                danfe_link = None
                links_col = cols[-1].find_all('a')
                for link in links_col:
                    txt = (link.text or link.get('data-original-title', '') or "").upper()
                    if 'XML' in txt: xml_link = link['href']
                    elif 'DANFE' in txt or 'PDF' in txt: danfe_link = link['href']
                
                if xml_link:
                    if self.download_file(xml_link, os.path.join(agent_dir, f"XML_{f_num}.xml")): files_count += 1
                if danfe_link:
                    if self.download_file(danfe_link, os.path.join(agent_dir, f"DANFE_{f_num}.pdf")): files_count += 1
                
                # Boletos
                for i in range(1, 4):
                    if i < len(cols):
                        b_el = cols[i].find('a')
                        if b_el and b_el.get('href'):
                            ts = datetime.now().strftime("%H%M%S")
                            if self.convert_boleto(b_el['href'], os.path.join(agent_dir, f"BOLETO_{f_num}_{i}_{ts}.pdf")):
                                files_count += 1
            
            if files_count > 0:
                self.logger.info(f"      [OK] {files_count} arquivos baixados para {trans_name}")
                
        except Exception as e:
            self.logger.error(f"Erro ao processar {trans_id}: {e}")

    def sanitize_folder_name(self, name):
        return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

    def download_file(self, url, dest_path):
        try:
            if not url.startswith('http'): url = urljoin("https://sys.sigetplus.com.br", url)
            r = requests.get(url, headers=self.headers, timeout=30)
            if r.status_code == 200:
                with open(dest_path, 'wb') as f: f.write(r.content)
                return True
        except: pass
        return False

    def convert_boleto(self, url, dest_path_pdf):
        try:
            if not url.startswith('http'): url = urljoin("https://sys.sigetplus.com.br", url)
            r = requests.get(url, headers=self.headers, timeout=30)
            if r.status_code == 200:
                if self.pdf_config:
                    pdfkit.from_string(r.text, dest_path_pdf, configuration=self.pdf_config, options={'quiet': '', 'encoding': 'utf-8'})
                else:
                    with open(dest_path_pdf.replace('.pdf', '.html'), 'w', encoding='utf-8') as f: f.write(r.text)
                return True
        except: pass
        return False

    def run(self):
        period = self.get_period_str()
        target_agents = self.get_agents()
        target_empresa = self.args.empresa
        
        self.logger.info(f"Iniciando SigetPlus V2 - Período: {period}")
        
        # Se não informou agentes, processa todos os agentes cadastrados no sistema
        # Mas o padrão é receber os agentes via argumento no Runner
        if not target_agents:
            self.logger.warning("Nenhum agente informado via --agente.")
            return

        # Para cada agente informado
        for agent_code in target_agents:
            self.logger.info(f"Processando Agente: {agent_code}")
            # Itera em TODAS as transmissoras V2
            for trans_id, trans_name in self.targets.items():
                self.processar_transmissora(trans_id, trans_name, agent_code, period, target_empresa or "DESCONHECIDO")

if __name__ == "__main__":
    bot = SigetPlusV2Robot()
    bot.run()
