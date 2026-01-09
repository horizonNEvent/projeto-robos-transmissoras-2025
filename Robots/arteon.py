import os
import requests
import json
import pdfkit
import tempfile
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from base_robot import BaseRobot

class ArteonRobot(BaseRobot):
    def __init__(self):
        super().__init__("arteon")
        self.base_url = "https://sys.sigetplus.com.br/cobranca/company/40/invoices"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        
        # Configuração wkhtmltopdf
        self.wkhtml_path = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        self.pdf_config = None
        if os.path.exists(self.wkhtml_path):
            self.pdf_config = pdfkit.configuration(wkhtmltopdf=self.wkhtml_path)
            
        self.pdf_options = {
            'page-size': 'A4',
            'encoding': 'UTF-8',
            'no-images': False,
            'enable-local-file-access': True
        }

    def carregar_referencia_empresas(self):
        try:
            json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Data', 'empresas.json')
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Erro ao carregar empresas.json: {e}")
            return {}

    def converter_html_pdf(self, html_content, dest_path):
        """Converte conteúdo HTML para PDF usando wkhtmltopdf."""
        try:
             # Se wkhtmltopdf não disponível, salvar HTML pode ser uma opção, mas o robô original tentava converter.
            if not self.pdf_config:
                self.logger.warning("wkhtmltopdf não configurado. Salvando como HTML.")
                with open(dest_path.replace('.pdf', '.html'), 'w', encoding='utf-8') as f:
                    f.write(html_content)
                return True

            with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as tf:
                tf.write(html_content)
                temp_html = tf.name
            
            try:
                pdfkit.from_file(temp_html, dest_path, options=self.pdf_options, configuration=self.pdf_config)
                return True
            except Exception as e:
                self.logger.error(f"Erro na conversão PDF: {e}")
                # Fallback: salva HTML
                with open(dest_path.replace('.pdf', '.html'), 'w', encoding='utf-8') as f:
                    f.write(html_content)
                return False
            finally:
                if os.path.exists(temp_html):
                    os.remove(temp_html)
        except Exception as e:
            self.logger.error(f"Erro geral convertendo boleto: {e}")
            return False

    def processar_agente(self, empresa_nome, ons_code, nome_ons):
        self.logger.info(f"Processando {empresa_nome} - {ons_code} ({nome_ons})")
        
        # Caminho base: downloads/TUST/ARTEON/BASE/ONS
        base_output_dir = self.get_output_path() 
        agent_dir = os.path.join(base_output_dir, empresa_nome, str(ons_code))
        
        
        url = f"{self.base_url}?agent={ons_code}"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                self.logger.warning(f"Erro HTTP {response.status_code} para {ons_code}")
                return

            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.select("table tbody tr")

            if not rows:
                self.logger.info("Nenhuma fatura encontrada.")
                return

            os.makedirs(agent_dir, exist_ok=True)
            total_baixados = 0

            for row in rows:
                cols = row.select('td')
                if not cols: continue

                transmissora_info = cols[0].text.strip()
                # Nome para arquivo: pegar ultimo pedaço
                nome_transmissora = transmissora_info.split('-')[-1].strip().replace(' ', '_').replace('/', '-')
                
                # Criar subpasta para transmissora (conforme original) ou salvar direto no agente?
                # O original fazia: download/ARTEON/BASE/ONS/NOME_TRANSMISSORA
                # Vamos manter para compatibilidade visual
                transmissora_path = os.path.join(agent_dir, nome_transmissora)
                os.makedirs(transmissora_path, exist_ok=True)

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

                # Boletos (Colunas 4,5,6 => indices 3,4,5)
                # O seletor original era bem específico
                boleto_links = row.select("td:nth-child(4) a, td:nth-child(5) a, td:nth-child(6) a")
                for i, blink in enumerate(boleto_links, 1):
                    href = blink.get('href')
                    if href:
                        b_url = href if href.startswith('http') else 'https://sys.sigetplus.com.br' + href
                        
                        nome_arq = f"Boleto_{nome_transmissora}_{timestamp}.pdf"
                        if i > 1:
                            nome_arq = f"Boleto_{nome_transmissora}_{timestamp}_{i}.pdf"
                        
                        dest = os.path.join(transmissora_path, nome_arq)
                        
                        self.logger.info(f"Baixando boleto: {nome_arq}")
                        try:
                            br = requests.get(b_url, headers=self.headers)
                            if br.status_code == 200:
                                if self.converter_html_pdf(br.text, dest):
                                    total_baixados += 1
                        except Exception as e:
                            self.logger.error(f"Falha download boleto {b_url}: {e}")

                # XML e DANFE
                xml_link = row.select_one("a[data-original-title='XML']")
                danfe_link = row.select_one("a[data-original-title='DANFE']")

                if xml_link:
                    href = xml_link['href']
                    x_url = href if href.startswith('http') else 'https://sys.sigetplus.com.br' + href
                    nome_xml = f"NFe_{nome_transmissora}_{timestamp}.xml"
                    dest_xml = os.path.join(transmissora_path, nome_xml)
                    try:
                        resp = requests.get(x_url, headers=self.headers)
                        with open(dest_xml, 'wb') as f:
                            f.write(resp.content)
                        self.logger.info(f"XML salvo: {nome_xml}")
                        total_baixados += 1
                    except Exception as e:
                        self.logger.error(f"Erro XML: {e}")

                if danfe_link:
                    href = danfe_link['href']
                    d_url = href if href.startswith('http') else 'https://sys.sigetplus.com.br' + href
                    nome_danfe = f"DANFE_{nome_transmissora}_{timestamp}.pdf"
                    dest_danfe = os.path.join(transmissora_path, nome_danfe)
                    try:
                        resp = requests.get(d_url, headers=self.headers)
                        with open(dest_danfe, 'wb') as f:
                            f.write(resp.content)
                        self.logger.info(f"DANFE salvo: {nome_danfe}")
                        total_baixados += 1
                    except Exception as e:
                        self.logger.error(f"Erro DANFE: {e}")

            self.logger.info(f"Finalizado ONS {ons_code}: {total_baixados} arquivos.")

        except Exception as e:
            self.logger.error(f"Erro processando agente {ons_code}: {e}")

    def run(self):
        empresas = self.carregar_referencia_empresas()
        target_empresa = self.args.empresa
        target_agents = self.get_agents()

        self.logger.info(f"Iniciando ArteonRobot")

        for empresa_nome, mapping in empresas.items():
            if target_empresa and target_empresa.upper() != empresa_nome.upper():
                continue
            
            for ons_code, nome_ons in mapping.items():
                if target_agents and str(ons_code) not in target_agents:
                    continue
                
                self.processar_agente(empresa_nome, ons_code, nome_ons)

if __name__ == "__main__":
    bot = ArteonRobot()
    bot.run()
