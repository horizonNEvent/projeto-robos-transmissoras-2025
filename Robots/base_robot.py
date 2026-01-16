import argparse
import logging
import os
import platform
import pdfkit
from datetime import datetime

class BaseRobot:
    """
    Contrato Mestre (Base) para todos os Robôs TUST.
    Padroniza caminhos e comportamentos para Windows e Linux.
    """

    def __init__(self, robot_name):
        self.robot_name = robot_name.lower()
        self.args = self._parse_args()
        self._setup_logging()
        
    def _parse_args(self):
        """Padroniza a entrada de dados."""
        parser = argparse.ArgumentParser(description=f"Robô TUST: {self.robot_name}")
        parser.add_argument("--empresa", help="Nome da Empresa")
        parser.add_argument("--user", help="Usuário de login")
        parser.add_argument("--password", help="Senha de login")
        parser.add_argument("--agente", help="Código ONS ou CNPJ")
        parser.add_argument("--competencia", help="Mês referência (Ex: 202512)")
        parser.add_argument("--output_dir", help="Pasta base para salvar os downloads")
        parser.add_argument("--headless", action="store_true", help="Executar em modo headless (sem interface)")
        return parser.parse_known_args()[0] # Evita erro com args extras do frontend

    def _setup_logging(self):
        """Configura o logger padrão."""
        logging.basicConfig(
            level=logging.INFO,
            format=f'[%(asctime)s] [{self.robot_name.upper()}] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self.logger = logging.getLogger(self.robot_name)

    def get_pdf_config(self):
        """
        Retorna a configuração do pdfkit/wkhtmltopdf de forma multiplataforma.
        """
        if platform.system() == "Windows":
            path_win = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
            if os.path.exists(path_win):
                return pdfkit.configuration(wkhtmltopdf=path_win)
        
        # No Linux (ou se não achou no caminho padrão do Win), tenta usar o binário global
        try:
            return pdfkit.configuration(wkhtmltopdf="wkhtmltopdf")
        except:
            self.logger.warning("wkhtmltopdf não detectado. Conversão de PDF pode falhar.")
            return None

    def get_output_path(self):
        """
        Retorna o caminho de saída base.
        Sempre relativo à raiz do projeto para funcionar em qualquer máquina.
        """
        if self.args.output_dir:
            return self.args.output_dir
        
        # Detecta raiz (volta 2 níveis de /Robots/base_robot.py)
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Adiciona pasta TUST para consistência com o backend
        base = os.path.join(root, "downloads", "TUST", self.robot_name.upper())
        os.makedirs(base, exist_ok=True)
        return base

    def get_agents(self):
        """Retorna lista de agentes do argumento."""
        if not self.args.agente: return []
        return [a.strip() for a in self.args.agente.split(',') if a.strip()]

    def run(self):
        raise NotImplementedError("O robô deve implementar o método run()")
