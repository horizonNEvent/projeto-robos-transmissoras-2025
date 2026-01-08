import requests
import json
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from base_robot import BaseRobot

class TropicaliaRobot(BaseRobot):
    """
    Robô para Portal Tropicalia, herdando do BaseRobot.
    """
    def __init__(self):
        super().__init__("tropicalia")
        
        # Headers Fixos
        self.headers = {
            "accept": "*/*",
            "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "content-type": "application/json",
            "origin": "https://nf-tropicalia-transmissora.cust.app.br",
            "referer": "https://nf-tropicalia-transmissora.cust.app.br/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        self.api_url = "https://ms-site.cap-tropicalia.cust.app.br/site/usuaria"

    def carregar_referencia_empresas(self):
        """Carrega o arquivo auxiliar empresas.json."""
        try:
            arquivo_json = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Data', 'empresas.json')
            with open(arquivo_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Erro ao carregar referencia de empresas: {e}")
            return {}

    def obter_competencia_alvo(self):
        """
        Se o usuário passou --competencia (ex: 11/2025), usa ela.
        Senão, calcula o mês anterior.
        Formato esperado pelo site: JANEIRO-2025 (Upper)
        """
        if self.args.competencia:
            # Tenta parsear 11/2025 -> NOVEMBRO-2025
            try:
                dt = datetime.strptime(self.args.competencia, "%m/%Y")
            except:
                try:
                    dt = datetime.strptime(self.args.competencia, "%Y-%m")
                except:
                    self.logger.warning(f"Formato de competência inválido: {self.args.competencia}. Usando automático.")
                    dt = None
        else:
            # Automático: Mês anterior
            hoje = datetime.now()
            primeiro_dia = hoje.replace(day=1)
            dt = primeiro_dia - timedelta(days=1)

        meses_pt = {
            1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL",
            5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
            9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
        }
        
        return f"{meses_pt[dt.month]}-{dt.year}"

    def download_file(self, url, filepath):
        """Baixa arquivo e loga resultado."""
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(r.content)
                self.logger.info(f"    [OK] Salvo: {os.path.basename(filepath)}")
                return True
            else:
                self.logger.error(f"    [ERRO] HTTP {r.status_code} ao baixar {os.path.basename(filepath)}")
        except Exception as e:
            self.logger.error(f"    [ERRO] Falha no download: {e}")
        return False

    def processar_ons(self, empresa_nome, ons_code, ons_name):
        """Processa um único ONS (Agente)."""
        self.logger.info(f"[{empresa_nome}] Consultando ONS {ons_code} ({ons_name})...")
        
        # Define pasta de destino
        path_final = os.path.join(self.get_output_path(), empresa_nome, str(ons_code))
        os.makedirs(path_final, exist_ok=True)

        params = {"numeroOns": ons_code}
        try:
            resp = requests.get(self.api_url, params=params, headers=self.headers, timeout=30)
            if resp.status_code != 200:
                self.logger.error(f"Erro na API Tropicalia: {resp.status_code}")
                return

            data = resp.json()
            competencia_alvo = self.obter_competencia_alvo()
            found = False

            for item in data:
                # Limpeza do período (ex: <b>FEVEREIRO-2025</b>)
                raw = item.get('periodoContabil', '')
                periodo = BeautifulSoup(raw, 'html.parser').get_text().strip().upper()

                if periodo == competencia_alvo:
                    found = True
                    self.logger.info(f"    Fatura encontrada para {periodo}")
                    
                    base_name = f"{ons_name}_{periodo.replace('-', '_')}"

                    # Baixar arquivos disponíveis
                    if item.get('linkDanfe'):
                        self.download_file(item['linkDanfe'], os.path.join(path_final, f"DANFE_{base_name}.pdf"))
                    if item.get('linkXml'):
                        self.download_file(item['linkXml'], os.path.join(path_final, f"XML_{base_name}.xml"))
                    if item.get('linkBoleto'):
                        self.download_file(item['linkBoleto'], os.path.join(path_final, f"BOLETO_{base_name}.pdf"))

            if not found:
                self.logger.warning(f"    Nenhuma fatura encontrada para competência {competencia_alvo}")

        except Exception as e:
            self.logger.error(f"Falha ao processar ONS {ons_code}: {e}")

    def run(self):
        """Loop principal do robô."""
        ref_empresas = self.carregar_referencia_empresas()
        agentes_alvo = self.get_agents()

        for empresa_nome, codigos_dict in ref_empresas.items():
            if self.args.empresa and self.args.empresa.strip().upper() != empresa_nome.strip().upper():
                continue

            for codigo_ons, nome_ons in codigos_dict.items():
                if agentes_alvo and str(codigo_ons).strip() not in agentes_alvo:
                    continue
                
                self.processar_ons(empresa_nome, codigo_ons, nome_ons)

if __name__ == "__main__":
    bot = TropicaliaRobot()
    bot.run()