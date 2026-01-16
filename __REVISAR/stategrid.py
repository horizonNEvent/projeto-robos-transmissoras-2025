import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
import pdfkit
import json

class StateGridRobot:
    def __init__(self):
        self.base_url = "https://sys.sigetplus.com.br/cobranca/company/15/invoices"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.config = pdfkit.configuration(wkhtmltopdf='C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe')

    # Carrega empresas do JSON compartilhado (Data/empresas.json)
    def carregar_empresas(self):
        # Caminho igual ao da assu
        arquivo_json = os.path.join(os.path.dirname(__file__), 'Data', 'empresas.json')
        try:
            if not os.path.exists(arquivo_json):
                print(f"Erro: Arquivo {arquivo_json} não encontrado!")
                return {}

            with open(arquivo_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Erro ao carregar empresas: {e}")
            return {}

    def get_invoices(self, agent_code):
        """Obtém as faturas para um determinado código de agente"""
        try:
            # Monta a URL inicial para pegar os cookies e o dropdown de meses
            url_sessao = f"{self.base_url}?agent={agent_code}"
            session = requests.Session()
            response = session.get(url_sessao, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Pega o mês selecionado ou o primeiro disponível
            select = soup.find('select', {'name': 'time'})
            option = None
            if select:
                option = select.find('option', selected=True) or select.find('option')
            
            latest_month = option['value'] if option else None
            
            if latest_month:
                print(f"    Filtrando competência: {latest_month}")
                url = f"{self.base_url}?agent={agent_code}&time={latest_month}"
                response = session.get(url, headers=self.headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
            
            # Encontra a tabela de faturas
            table = soup.find('table', {'class': 'table'})
            if not table:
                return pd.DataFrame([])
            
            # Extrai os dados da tabela
            data = []
            tbody = table.find('tbody')
            if not tbody:
                return pd.DataFrame([])

            for row in tbody.find_all('tr'):
                cols = row.find_all('td')
                if not cols:
                    continue
                
                num_cols = len(cols)
                if num_cols < 2:
                    # Geralmente é a linha "Nenhum registro encontrado"
                    continue

                # Indices baseados no HTML do StateGrid (Companhia 15):
                # 0: Transmissora
                # 1: Numero
                # 4: Boleto #1 (pode ter múltiplos)
                # 7: NFe (XML/DANFE)
                
                # Links de Boletos (coluna 4)
                boletos_links = []
                if num_cols > 4:
                    boletos_links = [a['href'] for a in cols[4].find_all('a', href=True)]
                
                # Links de XML e DANFE (coluna 7)
                xml_link = None
                danfe_link = None
                if num_cols > 7:
                    xml_tag = cols[7].find('a', {'data-original-title': 'XML'})
                    xml_link = xml_tag['href'] if xml_tag else None
                    
                    danfe_tag = cols[7].find('a', {'data-original-title': 'DANFE'})
                    danfe_link = danfe_tag['href'] if danfe_tag else None

                invoice = {
                    'transmissora': cols[0].text.strip(),
                    'numero_fatura': cols[1].text.strip(),
                    'parcelas': cols[2].text.strip() if num_cols > 2 else '',
                    'boletos': boletos_links,
                    'xml_link': xml_link,
                    'danfe_link': danfe_link
                }
                data.append(invoice)
            
            return pd.DataFrame(data)
            
        except requests.exceptions.RequestException as e:
            print(f"    Erro ao fazer requisição: {e}")
            return None
        except Exception as e:
            print(f"    Erro ao processar dados: {e}")
            return None

    def baixar_boleto(self, url, caminho_destino):
        """Download e conversão do boleto de HTML para PDF"""
        try:
            # Faz a requisição do HTML do boleto
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            # Converte o HTML para PDF
            pdfkit.from_string(response.text, caminho_destino, configuration=self.config)
            
            if os.path.exists(caminho_destino) and os.path.getsize(caminho_destino) > 0:
                print(f"    Boleto salvo: {os.path.basename(caminho_destino)}")
                return True
            else:
                return False
                
        except Exception as e:
            print(f"    Erro ao baixar boleto: {str(e)}")
            return False

    def download_files(self, df, agent_code, nome_ons, empresa_nome, base_path="C:\\Users\\Bruno\\Downloads\\TUST\\STATEGRID"):
        """Download dos arquivos XML, DANFE e Boleto"""
        # Cria pasta: Raiz / Empresa / CodigoONS (Padrão ASSU)
        output_path = os.path.join(base_path, empresa_nome, str(agent_code))
        os.makedirs(output_path, exist_ok=True)
        
        # Para StateGrid, os arquivos são da última competência
        date_path = output_path
        
        for idx, row in df.iterrows():
            try:
                # Cria pasta para a transmissora (opcional se quiser unificar na ONS, mas StateGrid tem múltiplas por ONS)
                transmissora_texto = row['transmissora']
                transmissora_name = sanitizar_nome(transmissora_texto.split(' - ')[1].strip() if ' - ' in transmissora_texto else transmissora_texto)
                
                transmissora_path = os.path.join(date_path, transmissora_name)
                os.makedirs(transmissora_path, exist_ok=True)
                
                # Download XML
                if row['xml_link']:
                    try:
                        xml_response = requests.get(row['xml_link'], headers=self.headers)
                        xml_response.raise_for_status()
                        
                        xml_filename = row['xml_link'].split('/')[-1]
                        if not xml_filename.endswith('.xml'):
                            xml_filename = f"{row['numero_fatura']}.xml"
                        
                        xml_path = os.path.join(transmissora_path, xml_filename)
                        with open(xml_path, 'wb') as f:
                            f.write(xml_response.content)
                        print(f"  XML salvo: {xml_filename}")
                    except Exception as e:
                        print(f"  Erro ao baixar XML {row['numero_fatura']}: {e}")
                
                # Download DANFE
                if row['danfe_link']:
                    try:
                        danfe_response = requests.get(row['danfe_link'], headers=self.headers)
                        danfe_response.raise_for_status()
                        
                        danfe_filename = f"{row['numero_fatura']}_danfe.pdf"
                        danfe_path = os.path.join(transmissora_path, danfe_filename)
                        with open(danfe_path, 'wb') as f:
                            f.write(danfe_response.content)
                        print(f"  DANFE salvo: {danfe_filename}")
                    except Exception as e:
                        print(f"  Erro ao baixar DANFE {row['numero_fatura']}: {e}")

                # Download Boletos
                if row['boletos']:
                    for idx_bol, boleto_url in enumerate(row['boletos'], 1):
                        try:
                            boleto_filename = f"{row['numero_fatura']}_boleto_{idx_bol}.pdf"
                            boleto_path = os.path.join(transmissora_path, boleto_filename)
                            self.baixar_boleto(boleto_url, boleto_path)
                        except Exception as e:
                            print(f"  Erro ao baixar Boleto {idx_bol} da fatura {row['numero_fatura']}: {e}")
                        
            except Exception as e:
                print(f"  Erro ao processar fatura {row['numero_fatura']}: {e}")

    def process_all_agents(self, empresas):
        """Processa todos os agentes fornecidos: {Empresa: {CNS: Nome}}"""
        for empresa_nome, mapping in empresas.items():
            print(f"\nProcessando empresa: {empresa_nome}")
            for agent_code, nome_ons in mapping.items():
                try:
                    print(f"\n> Ponto: {nome_ons} (ONS: {agent_code})")
                    df = self.get_invoices(agent_code)
                    if df is not None and not df.empty:
                        print(f"  Encontradas {len(df)} faturas")
                        self.download_files(df, agent_code, nome_ons, empresa_nome)
                    else:
                        print(f"  Nenhuma fatura encontrada")
                except Exception as e:
                    print(f"  Erro ao processar agente {agent_code}: {e}")

def sanitizar_nome(nome):
    import re
    nome_limpo = re.sub(r'[<>:"/\\|?*\n\r]', ' ', nome)
    nome_limpo = re.sub(r'\s+', ' ', nome_limpo).strip()
    return nome_limpo

# Exemplo de uso
if __name__ == "__main__":
    robot = StateGridRobot()
    empresas = robot.carregar_empresas()
    robot.process_all_agents(empresas)
    print("\nProcessamento concluído!")
