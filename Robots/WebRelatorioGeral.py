"""
WebRelatorioGeral - Baixa o Relatório Geral de Cadastro de Agentes (XLSX)
via Sintegre/SAAT (ONS), recebendo login e senha.

Uso direto:
    python Robots/WebRelatorioGeral.py --user EMAIL --password SENHA
    python Robots/WebRelatorioGeral.py --user EMAIL --password SENHA --exibir 2 --output_dir PASTA

--exibir: 0=Dados Gerais, 1=Representantes, 2=Ambos (padrão).
"""

import os
import sys
from datetime import datetime

# Garante que a pasta Robots esteja no path para importar módulos locais
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

from relatorio_geral import baixar_relatorio_com_login


class WebRelatorioGeralRobot(BaseRobot):
    """Baixa o Relatório Geral de Cadastro (XLSX) do SAAT/ONS via login Sintegre."""

    def __init__(self):
        super().__init__("webrelatoriogeral")
        # Opção de exibição (0/1/2). Lida manualmente pois BaseRobot não define.
        self.exibir = self._parse_exibir()

    @staticmethod
    def _parse_exibir() -> str:
        """Lê --exibir dos argumentos sem quebrar o parser padrão do BaseRobot."""
        argv = sys.argv
        for i, arg in enumerate(argv):
            if arg == "--exibir" and i + 1 < len(argv):
                val = argv[i + 1].strip()
                return val if val in ("0", "1", "2") else "2"
            if arg.startswith("--exibir="):
                val = arg.split("=", 1)[1].strip()
                return val if val in ("0", "1", "2") else "2"
        return "2"

    def run(self):
        login = self.args.user
        senha = self.args.password

        if not login or not senha:
            self.logger.error("Login (--user) e Senha (--password) são obrigatórios.")
            sys.exit(1)

        output_dir = self.get_output_path()
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = os.path.join(output_dir, f"RelatorioGeralCadastro_{timestamp}.xlsx")

        self.logger.info(
            "Baixando Relatório Geral de Cadastro (exibir=%s)...", self.exibir
        )
        try:
            caminho = baixar_relatorio_com_login(
                login.strip(),
                senha,
                self.logger,
                exibir=self.exibir,
                destino=destino,
            )
        except Exception as exc:
            self.logger.error("Falha ao baixar o Relatório Geral: %s", exc)
            sys.exit(1)

        self.logger.info("Relatório salvo em: %s", caminho)
        print(str(caminho))


if __name__ == "__main__":
    robot = WebRelatorioGeralRobot()
    robot.run()
