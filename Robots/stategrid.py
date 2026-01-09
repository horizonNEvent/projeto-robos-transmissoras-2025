import requests
import pandas as pd
import os
import re
import pdfkit
from bs4 import BeautifulSoup
from datetime import datetime

# Import BaseRobot
try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

class StateGridRobot(BaseRobot):
    """
    Robô para StateGrid (via SigetPlus).
    URL: https://sys.sigetplus.com.br/cobranca/company/15/invoices
    Autenticação: Aparentemente pública via query param ?agent=CODE (ou IP whitelist).
    """

    def __init__(self):
        super().__init__("stategrid")
        self.base_url = "https://sys.sigetplus.com.br/cobranca/company/15/invoices"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # Configuração do wkhtmltopdf
        path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        if os.path.exists(path_wkhtmltopdf):
            self.config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        else:
            self.logger.warning(f"wkhtmltopdf não encontrado em {path_wkhtmltopdf}. Conversão de boleto HTML->PDF falhará.")
            self.config = None

    def sanitizar_nome(self, nome):
        nome_limpo = re.sub(r'[<>:"/\\|?*\n\r]', ' ', nome)
        return re.sub(r'\s+', ' ', nome_limpo).strip()

    def get_invoices(self, agent_code, target_competencia=None):
        """
        Obtém as faturas.
        target_competencia: string YYYYMM (ex: 202512)
        """
        try:
            self.logger.info(f"Buscando faturas para Agente {agent_code}...")
            session = requests.Session()
            
            # 1. Acessa página inicial do agente (pega cookies e lista de meses)
            url_sessao = f"{self.base_url}?agent={agent_code}"
            response = session.get(url_sessao, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 2. Determina o mês (time)
            select = soup.find('select', {'name': 'time'})
            selected_month_value = None
            
            if select:
                if target_competencia:
                    # Converte YYYYMM (202512) para formato do SigetPlus (provavelmente YYYY-MM ou MM/YYYY)
                    # O script original pegava o value direto. Vamos assumir YYYY-MM se for padrão web, 
                    # mas precisamos ver as options.
                    # Vamos varrer as options para tentar dar match.
                    
                    target_ano = target_competencia[:4]
                    target_mes = target_competencia[4:6]
                    
                    options = select.find_all('option')
                    for opt in options:
                        val = opt.get('value') # Ex: 2025-12
                        txt = opt.text.strip() # Ex: Dezembro/2025
                        
                        # Tenta match no value (ex: 2025-12)
                        if val and f"{target_ano}-{target_mes}" in val:
                            selected_month_value = val
                            break
                        # Tenta match no texto (mes/ano) - Logica simples
                        # ...
                        
                    if not selected_month_value:
                        self.logger.warning(f"Competência {target_competencia} não encontrada nas opções disponíveis.")
                        # Se não achou, não seleciona nada? Ou pega o padrão?
                        # Vamos retornar vazio para respeitar o filtro.
                        return None, pd.DataFrame([])
                else:
                    # Pega o selecionado ou o primeiro (Lógica Original: Mais Recente)
                    option = select.find('option', selected=True) or select.find('option')
                    if option: selected_month_value = option['value']

            if selected_month_value:
                self.logger.info(f"Filtrando mês (value): {selected_month_value}")
                url = f"{self.base_url}?agent={agent_code}&time={selected_month_value}"
                response = session.get(url, headers=self.headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
            
            # 3. Extrai Tabela
            table = soup.find('table', {'class': 'table'})
            if not table:
                self.logger.warning("Tabela de faturas não encontrada.")
                return None, pd.DataFrame([])
            
            data = []
            tbody = table.find('tbody')
            if not tbody: return None, pd.DataFrame([])

            for row in tbody.find_all('tr'):
                cols = row.find_all('td')
                if not cols or len(cols) < 2: continue
                
                # Mapeamento colunas StateGrid (Company 15)
                # 0: Transmissora
                # 1: Numero
                # 4: Boleto
                # 7: NFe (XML/DANFE)
                
                # Boletos
                boletos_links = []
                if len(cols) > 4:
                    boletos_links = [a['href'] for a in cols[4].find_all('a', href=True)]
                
                # XML/DANFE
                xml_link = None
                danfe_link = None
                if len(cols) > 7:
                    xml_tag = cols[7].find('a', {'data-original-title': 'XML'})
                    if xml_tag: xml_link = xml_tag['href']
                    
                    danfe_tag = cols[7].find('a', {'data-original-title': 'DANFE'})
                    if danfe_tag: danfe_link = danfe_tag['href']

                data.append({
                    'transmissora': cols[0].text.strip(),
                    'numero_fatura': cols[1].text.strip(),
                    'boletos': boletos_links,
                    'xml_link': xml_link,
                    'danfe_link': danfe_link
                })
            
            return selected_month_value, pd.DataFrame(data)

        except Exception as e:
            self.logger.error(f"Erro ao obter faturas: {e}")
            return None, pd.DataFrame([])

    def baixar_boleto(self, url, caminho_destino):
        try:
            if not self.config: 
                return False
                
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            pdfkit.from_string(response.text, caminho_destino, configuration=self.config)
            
            if os.path.exists(caminho_destino) and os.path.getsize(caminho_destino) > 0:
                self.logger.info(f"Boleto Convertido: {os.path.basename(caminho_destino)}")
                return True
        except Exception as e:
            self.logger.error(f"Erro conversão boleto: {e}")
        return False

    def baixar_arquivo(self, url, caminho):
        try:
            r = requests.get(url, headers=self.headers)
            r.raise_for_status()
            with open(caminho, 'wb') as f:
                f.write(r.content)
            self.logger.info(f"Baixado: {os.path.basename(caminho)}")
            return True
        except Exception as e:
            self.logger.error(f"Erro download {os.path.basename(caminho)}: {e}")
            return False

    def run(self):
        agente_ons = self.args.agente
        if not agente_ons:
            self.logger.error("Código ONS obrigatorio (--agente).")
            return

        competencia = self.args.competencia # YYYYMM
        
        mes_str, df = self.get_invoices(agente_ons, competencia)
        
        if df is None or df.empty:
            self.logger.info("Nenhuma fatura encontrada.")
            return

        # Pasta de Saída
        base_output = self.get_output_path()
        # Subpasta Agente
        agent_dir = os.path.join(base_output, str(agente_ons))
        os.makedirs(agent_dir, exist_ok=True)
        
        self.logger.info(f"Processando {len(df)} faturas. Saída: {agent_dir}")
        
        for idx, row in df.iterrows():
            # Pasta Transmissora
            transmissora_raw = row['transmissora']
            # Limpa nome (remove codigo ' - ')
            if ' - ' in transmissora_raw:
                t_nome = transmissora_raw.split(' - ')[1].strip()
            else:
                t_nome = transmissora_raw
            
            t_nome = self.sanitizar_nome(t_nome)
            t_dir = os.path.join(agent_dir, t_nome)
            os.makedirs(t_dir, exist_ok=True)
            
            num = row['numero_fatura']
            
            # Baixa XML
            if row['xml_link']:
                xml_name = f"NFe_{t_nome}_{num}.xml" # Padronizacao TUST
                self.baixar_arquivo(row['xml_link'], os.path.join(t_dir, xml_name))
            
            # Baixa DANFE
            if row['danfe_link']:
                danfe_name = f"DANFE_{t_nome}_{num}.pdf"
                self.baixar_arquivo(row['danfe_link'], os.path.join(t_dir, danfe_name))
            
            # Baixa Boletos (Convertendo HTML -> PDF)
            if row['boletos']:
                for i, bol_url in enumerate(row['boletos'], 1):
                    bol_name = f"Boleto_{t_nome}_{num}_{i}.pdf"
                    self.baixar_boleto(bol_url, os.path.join(t_dir, bol_name))

if __name__ == "__main__":
    robot = StateGridRobot()
    robot.run()
