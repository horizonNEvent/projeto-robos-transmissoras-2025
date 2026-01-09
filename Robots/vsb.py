import requests
import os
import zipfile
import json
from datetime import datetime, timedelta

try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

class VSBRobot(BaseRobot):
    """
    Robô para VSB (Vila do Conde / Santa Bárbara).
    URL: https://www.vsbtrans.com.br
    Autenticação: Via Código ONS na URL.
    """

    def __init__(self):
        super().__init__("vsb")
        self.base_url = "https://www.vsbtrans.com.br"
        self.headers = {
            "accept": "*/*",
            "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "referer": "https://www.vsbtrans.com.br/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }

    def formatar_competencia(self, competencia_str):
        """Converte YYYYMM para YYYY.MM"""
        if not competencia_str or len(competencia_str) != 6:
            # Default: Mês anterior
            hoje = datetime.now()
            mes_anterior = hoje.replace(day=1) - timedelta(days=1)
            return mes_anterior.strftime("%Y.%m")
        return f"{competencia_str[:4]}.{competencia_str[4:]}"

    def download_and_extract_zip(self, zip_rel_url, output_dir):
        try:
            full_url = f"{self.base_url}{zip_rel_url}"
            self.logger.info(f"Baixando ZIP: {full_url}")
            
            resp = requests.get(full_url, headers=self.headers, timeout=60)
            if resp.status_code == 200:
                zip_filename = "temp_download.zip"
                zip_path = os.path.join(output_dir, zip_filename)
                
                with open(zip_path, 'wb') as f:
                    f.write(resp.content)
                
                # Extrair
                self.logger.info("Extraindo arquivos...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(output_dir)
                
                os.remove(zip_path) # Limpa temp
                self.logger.info("Extração concluída.")
                return True
            else:
                self.logger.error(f"Erro download ZIP: Status {resp.status_code}")
        except Exception as e:
            self.logger.error(f"Exceção download ZIP: {e}")
        return False

    def run(self):
        cod_ons = self.args.agente
        if not cod_ons:
            self.logger.error("Código ONS obrigatório (--agente).")
            return

        # Padrão VSB exige YYYY.MM
        data_param = self.formatar_competencia(self.args.competencia)
        self.logger.info(f"Iniciando VSB para ONS {cod_ons} - Competência {data_param}...")

        url = f"{self.base_url}/getFiles.php?codigo={cod_ons}&data={data_param}"
        
        try:
            resp = requests.get(url, headers=self.headers, timeout=30)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    zip_url = data.get("zipUrl")
                    
                    if zip_url:
                        base_path = self.get_output_path()
                        out_dir = os.path.join(base_path, str(cod_ons))
                        os.makedirs(out_dir, exist_ok=True)
                        
                        self.download_and_extract_zip(zip_url, out_dir)
                    else:
                        self.logger.warning(f"Nenhum arquivo encontrado (zipUrl vazio) para {data_param}.")
                except json.JSONDecodeError:
                     self.logger.error(f"Erro ao decodificar JSON. Resposta: {resp.text[:100]}")
            else:
                self.logger.error(f"Erro API: Status {resp.status_code}")
                
        except Exception as e:
            self.logger.error(f"Erro fatal: {e}")

if __name__ == "__main__":
    robot = VSBRobot()
    robot.run()
