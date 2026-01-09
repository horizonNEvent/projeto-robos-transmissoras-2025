import os
import requests
import json
import pdfkit
import tempfile
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from base_robot import BaseRobot

class AguaVermelhaRobot(BaseRobot):
    def __init__(self):
        super().__init__("aguavermelha")
        self.base_url = "https://sys.sigetplus.com.br/cobranca/transmitter/1327/invoices"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        
        # Configuração do wkhtmltopdf
        # Tenta localizar no caminho padrão do Windows ou no PATH do sistema
        self.wkhtml_path = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        self.pdf_config = None
        
        if os.path.exists(self.wkhtml_path):
            self.pdf_config = pdfkit.configuration(wkhtmltopdf=self.wkhtml_path)
        else:
            # Tenta sem caminho fixo (Linux/Path)
            try:
                self.pdf_config = pdfkit.configuration()
            except:
                self.logger.warning("⚠️ wkhtmltopdf não encontrado. Boletos serão salvos apenas como HTML.")

    def carregar_referencia_empresas(self):
        """Carrega Data/empresas.json"""
        try:
            json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Data', 'empresas.json')
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Erro ao carregar empresas.json: {e}")
            return {}

    def get_period_str(self):
        """Define a competência (YYYYMM). Argumento > Mês Anterior."""
        if self.args.competencia:
            # Remove / ou - para normalizar YYYYMM
            c = self.args.competencia.replace('/', '').replace('-', '')
            if len(c) == 6:
                return c
            self.logger.warning(f"Formato de competência {c} pode ser inválido. Usando calculado.")

        now = datetime.now()
        if now.month == 1:
            mes = 12
            ano = now.year - 1
        else:
            mes = now.month - 1
            ano = now.year
        return f"{ano}{mes:02d}"

    def get_invoices(self, agent_code, period):
        """Faz o scraping da tabela de faturas."""
        try:
            url = f"{self.base_url}?agent={agent_code}"
            if period:
                url += f"&time={period}"
            
            self.logger.info(f"Acessando: {url}")
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Períodos disponíveis
            periods = []
            select = soup.find('select', {'name': 'time'})
            if select:
                periods = [opt['value'] for opt in select.find_all('option')]

            # Se pediu período específico e ele não tá na lista, mas a lista existe, alerta
            # Mas o site pode retornar vazio se o periodo nao existe
            
            table = soup.find('table', {'class': 'table-striped'})
            if not table:
                return pd.DataFrame(), periods
                
            rows = table.find_all('tr')[1:]
            data = []
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 7: continue
                
                # Parsing das colunas
                fatura_el = cols[1].find('a')
                fatura_num = fatura_el.text.strip() if fatura_el else ""
                
                parcelas = cols[2].text.strip() # Não usado mas extraído
                
                boletos = []
                for i in range(3, 6):
                    b_el = cols[i].find('a')
                    if b_el:
                        boletos.append({'data': b_el.text.strip(), 'link': b_el['href']})
                    else:
                        boletos.append(None)
                
                xml_link = None
                danfe_link = None
                
                # Links na última coluna
                links = cols[6].find_all('a')
                for link in links:
                    txt = link.text or link.get('data-original-title', '')
                    if 'XML' in txt: xml_link = link['href']
                    elif 'DANFE' in txt: danfe_link = link['href']
                
                # Agente Info (Coluna 0)
                # "CODE - NAME"
                agent_el = cols[0].text.strip().split(' - ')
                ag_code = agent_el[0] if len(agent_el) > 0 else agent_code
                ag_name = agent_el[1] if len(agent_el) > 1 else "Unknown"

                data.append({
                    'agent_code': ag_code,
                    'agent_name': ag_name,
                    'fatura_numero': fatura_num,
                    'boletos': boletos,
                    'xml_link': xml_link,
                    'danfe_link': danfe_link
                })
                
            return pd.DataFrame(data), periods

        except Exception as e:
            self.logger.error(f"Erro ao buscar faturas: {e}")
            return pd.DataFrame(), []

    def download_file(self, url, dest_path):
        try:
            r = requests.get(url, headers=self.headers)
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                f.write(r.content)
            return True
        except Exception as e:
            self.logger.error(f"Erro download {os.path.basename(dest_path)}: {e}")
            return False

    def convert_boleto(self, url, dest_path_pdf):
        """Baixa HTML e converte para PDF. Fallback: Salva HTML."""
        try:
            r = requests.get(url, headers=self.headers)
            r.raise_for_status()
            
            # Salva HTML temporário
            with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as tmp:
                tmp.write(r.text)
                tmp_path = tmp.name
                
            # Tenta converter
            ok = False
            if self.pdf_config:
                try:
                    options = {'quiet': '', 'encoding': 'utf-8'}
                    pdfkit.from_file(tmp_path, dest_path_pdf, options=options, configuration=self.pdf_config)
                    ok = True
                except Exception as e:
                    self.logger.warning(f"Erro wkhtmltopdf: {e}")
            
            # Limpa temp
            try: os.unlink(tmp_path)
            except: pass

            if ok:
                return True
            else:
                # Fallback: Salva o HTML original
                html_path = dest_path_pdf.replace('.pdf', '.html')
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(r.text)
                self.logger.warning(f"Salvo como HTML (PDF falhou): {os.path.basename(html_path)}")
                return True

        except Exception as e:
            self.logger.error(f"Erro processando boleto: {e}")
            return False

    def run(self):
        period = self.get_period_str()
        empresas = self.carregar_referencia_empresas()
        
        # Filtros
        target_empresa = self.args.empresa
        target_agents = self.get_agents() # set de strings
        
        # Caminho Base de saída
        base_output_dir = self.get_output_path()
        # Nota: O BaseRobot define output_dir como downloads/TUST/AGUAVERMELHA por padrão

        self.logger.info(f"Iniciando Água Vermelha - Competência: {period}")

        total_files = 0

        for base, mapping in empresas.items():
            if target_empresa and target_empresa.upper() != base.upper():
                continue
            
            for ons_code, agent_name in mapping.items():
                ons_str = str(ons_code)
                if target_agents and ons_str not in target_agents:
                    continue
                
                self.logger.info(f"Verificando {base} - {agent_name} ({ons_str})...")
                
                df, periods = self.get_invoices(ons_str, period)
                
                if df.empty:
                    # Se não achou na competência, avisa quais existem
                    if periods:
                        self.logger.info(f"  Nada para {period}. Disponíveis: {periods[:3]}...")
                    else:
                        self.logger.info(f"  Nenhuma fatura encontrada.")
                    continue
                
                # Processa Faturas
                # Estrutura de Pastas: BASE / ONS / ARQUIVOS (conforme padrão TUST)
                # O BaseRobot espera que coloquemos tudo em output_dir. 
                # Vamos criar subpastas: output_dir/BASE/ONS
                
                agent_dir = os.path.join(base_output_dir, base, ons_str)
                os.makedirs(agent_dir, exist_ok=True)
                
                for _, row in df.iterrows():
                    fatura_id = row['fatura_numero']
                    
                    # XML
                    if row['xml_link']:
                        if self.download_file(row['xml_link'], os.path.join(agent_dir, f"NFe_{fatura_id}.xml")):
                            total_files += 1
                            print(f"  [XML] {fatura_id}")
                            
                    # DANFE
                    if row['danfe_link']:
                        if self.download_file(row['danfe_link'], os.path.join(agent_dir, f"DANFE_{fatura_id}.pdf")):
                            total_files += 1
                            print(f"  [PDF] DANFE {fatura_id}")
                            
                    # Boletos
                    for i, bol in enumerate(row['boletos']):
                        if bol and bol['link']:
                            ts = datetime.now().strftime("%H%M%S")
                            fname = os.path.join(agent_dir, f"Boleto_{fatura_id}_{i+1}_{ts}.pdf")
                            if self.convert_boleto(bol['link'], fname):
                                total_files += 1
                                print(f"  [BOL] Boleto {i+1}")

        self.logger.info(f"Finalizado. {total_files} arquivos baixados.")

if __name__ == "__main__":
    bot = AguaVermelhaRobot()
    bot.run()
