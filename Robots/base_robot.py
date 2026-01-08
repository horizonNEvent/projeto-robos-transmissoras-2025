import argparse
import logging
import os
from datetime import datetime

class BaseRobot:
    """
    Contrato Mestre (Base) para todos os Robôs TUST.
    Responsável por: 
    - Lógica de Parâmetros (Argparse)
    - Padronização de Logs
    - Gestão de Pastas de Download
    - Helper methods (get_agents)
    """

    def __init__(self, robot_name):
        self.robot_name = robot_name.lower()
        self.args = self._parse_args()
        self._setup_logging()
        
    def _parse_args(self):
        """Padroniza a entrada de dados vinda do Agendador ou Manual."""
        parser = argparse.ArgumentParser(description=f"Robô TUST: {self.robot_name}")
        parser.add_argument("--empresa", help="Nome da Empresa (ex: AETE, RE, AE, DE)")
        parser.add_argument("--user", help="Usuário de login")
        parser.add_argument("--password", help="Senha de login")
        parser.add_argument("--agente", help="Código ONS ou lista de códigos separados por vírgula")
        parser.add_argument("--competencia", help="Mês referência (Ex: 11/2025 para CNT ou conforme o robô)")
        parser.add_argument("--output_dir", help="Pasta base para salvar os downloads")
        
        return parser.parse_args()

    def _setup_logging(self):
        """Configura o logger com o nome do robô."""
        logging.basicConfig(
            level=logging.INFO,
            format=f'[%(asctime)s] [{self.robot_name.upper()}] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self.logger = logging.getLogger(self.robot_name)

    def get_output_path(self):
        """Determina a pasta de download."""
        if self.args.output_dir:
            return self.args.output_dir
        
        # Padrão local caso não seja passado via argumento
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(root, "downloads", self.robot_name.upper())

    def get_agents(self):
        """Helper para retornar a lista de agentes limpa."""
        if not self.args.agente:
            return []
        return [a.strip() for a in self.args.agente.split(',') if a.strip()]

    def run(self):
        """Método abstrato que deve ser implementado pelo robô filho."""
        raise NotImplementedError("O robô deve implementar o método run()")
