
import os
import requests
import json
import base64
import re
import sys
from datetime import datetime

# Ajuste de path para importar BaseRobot se necessário
try:
    from Robots.base_robot import BaseRobot
except ImportError:
    # Caso rode direto da pasta Robots
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from Robots.base_robot import BaseRobot

class CemigRobot(BaseRobot):
    """
    Robô para Cemig API (Portal Novo).
    """
    def __init__(self):
        super().__init__("cemig")
        self.url = "https://novoportal.cemig.com.br/wp-json/consulta-ons/v1/dados"
        
        # Mapeamento de Empresas (Código -> Nome da Pasta)
        self.EMPRESAS_MAP = {
            "510": "1004 - CEMIG",
            "720": "1071 - CENTROESTE DE MINAS",
            "740": "1139 - SLTE"
        }

    def process_agent(self, cod_ons, mes, ano, base_output_dir):
        """
        Executa a busca para um agente (cod_ons) e data específicos.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://novoportal.cemig.com.br",
            "Referer": "https://novoportal.cemig.com.br/faturas/consulta-para-usuarios-da-fatura-da-rede-basica-de-transmissao/",
        }

        payload = {
            "codOns": cod_ons,
            "mes": mes,
            "ano": ano
        }

        try:
            self.logger.info(f"🔎 Buscando faturas para ONS {cod_ons} - {mes}/{ano}...")
            response = requests.post(self.url, headers=headers, data=payload)
            response.raise_for_status()
            
            try:
                json_resp = response.json()
            except json.JSONDecodeError:
                self.logger.error(f"❌ Resposta inválida (não JSON) do servidor para ONS {cod_ons}.")
                return

            titulos = json_resp.get('data', {}).get('titulos', [])
            
            if not titulos:
                self.logger.info(f"⚪ Nenhuma fatura encontrada para ONS {cod_ons} em {mes}/{ano}.")
                return

            self.logger.info(f"📄 Processando {len(titulos)} faturas...")

            for item in titulos:
                # Identificar Empresa
                bukrs = item.get('bukrs')
                folder_name = self.EMPRESAS_MAP.get(str(bukrs), f"Empresa_{bukrs}")
                
                # Estrutura: OUTPUT / AGENTE / ...
                agent_dir = os.path.join(base_output_dir, str(cod_ons))
                company_dir = os.path.join(agent_dir, folder_name)
                
                if not os.path.exists(company_dir):
                    os.makedirs(company_dir)

                # Dados do documento
                doc_num = item.get('xblnr', 'doc')
                safe_doc_num = re.sub(r'[\\/*?:"<>|]', "", str(doc_num))

                links = item.get('links', {})
                
                # Salvar XML
                if 'xml_b64' in links and links['xml_b64']:
                    try:
                        content = base64.b64decode(links['xml_b64'])
                        filename = f"Fatura_{safe_doc_num}.xml"
                        path = os.path.join(company_dir, filename)
                        with open(path, "wb") as f:
                            f.write(content)
                        self.logger.info(f"  💾 Salvo XML: {folder_name}/{filename}")
                    except Exception as e:
                        self.logger.error(f"  ❌ Erro ao salvar XML {safe_doc_num}: {e}")

                # Salvar Boleto
                if 'boleto_b64' in links and links['boleto_b64']:
                    try:
                        content = base64.b64decode(links['boleto_b64'])
                        filename = f"Boleto_{safe_doc_num}.pdf"
                        path = os.path.join(company_dir, filename)
                        with open(path, "wb") as f:
                            f.write(content)
                        self.logger.info(f"  💾 Salvo PDF: {folder_name}/{filename}")
                    except Exception as e:
                        self.logger.error(f"  ❌ Erro ao salvar Boleto {safe_doc_num}: {e}")
                    
        except Exception as e:
            self.logger.error(f"❌ Erro Crítico: {e}")

    def run(self):
        self.logger.info("🚀 Iniciando Robô Cemig...")
        
        mes = None
        ano = None
        
        # Lógica de data
        if self.args.competencia:
            c = self.args.competencia.replace('/', '').replace('-', '')
            if len(c) == 6:
                if int(c) > 200000: # YYYYMM
                     ano = c[:4]
                     mes = c[4:]
                else: # MMYYYY
                     mes = c[:2]
                     ano = c[2:]
            elif len(c) == 7 and '/' in self.args.competencia:
                p = self.args.competencia.split('/')
                mes, ano = p[0], p[1]

        if not mes or not ano:
            now = datetime.now()
            mes = f"{now.month:02d}"
            ano = f"{now.year}"
            self.logger.info(f"⚠️ Competência não informada. Usando atual: {mes}/{ano}")

        agents = self.get_agents()
        if not agents:
             self.logger.error("❌ Nenhum agente informado (--agente).")
             return

        base_output_dir = self.get_output_path()

        for cod_ons in agents:
            self.process_agent(cod_ons, mes, ano, base_output_dir)
            
        self.logger.info("🏁 Execução Concluída.")

if __name__ == "__main__":
    robot = CemigRobot()
    robot.run()
