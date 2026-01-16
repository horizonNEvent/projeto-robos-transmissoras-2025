import os
import logging
from datetime import datetime
import sys

# Adicionar o diretório pai ao caminho para poder importar os módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# Importar a classe base (SharePoint desativado na RobotBase)
from IE.robot_base import RobotBase

# Configuração de logging — comentada a pedido (não criar arquivo de log)
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler(),
#         logging.FileHandler(f"log_ieriachogrande_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
#     ]
# )
logger = logging.getLogger("IERIACHOGRANDE")

# Configuração para Ieriachogrande
IE_NOME = "IERIACHOGRANDE"
IE_URL = "https://faturamento.ieriachogrande.com.br"
# Caminho para o arquivo de credenciais específico
CAMINHO_CREDENCIAIS = os.path.join(os.path.dirname(__file__), "Data", "empresas.cteep.json")

MAPEAMENTO_CODIGOS = {
    "IERG - 005/2021 - IERG": "1354"
}

class IeriachograndeRobot(RobotBase):
    """Classe específica para o robô Ieriachogrande"""
    
    def __init__(self, sharepoint_disponivel=False):
        """
        Inicializa o robô Ieriachogrande
        
        Parâmetros:
        - sharepoint_disponivel: Flag indicando se o SharePoint está disponível
        """
        super().__init__(
            nome_ie=IE_NOME,
            url_ie=IE_URL,
            mapeamento_codigos=MAPEAMENTO_CODIGOS,
            sharepoint_disponivel=False,  # sempre local; SharePoint desativado na base
            caminho_credenciais=CAMINHO_CREDENCIAIS
        )

def main():
    """
    Função principal que configura o robô e processa as faturas
    """
    logger.info("=" * 80)
    logger.info("Iniciando o processo de download das faturas da IERIACHOGRANDE (salvamento local)...")
    logger.info("=" * 80)
    
    # Inicializa o robô (SharePoint desativado; salvamento local na pasta downloads do projeto)
    robot = IeriachograndeRobot(sharepoint_disponivel=False)
    
    # Verifica se as credenciais foram carregadas corretamente
    if not robot.credenciais:
        logger.error(f"Nenhuma credencial válida encontrada no arquivo: {CAMINHO_CREDENCIAIS}")
        return
    logger.info(f"Foram carregadas {len(robot.credenciais)} credenciais de {CAMINHO_CREDENCIAIS}.")
    
    # Processar todas as empresas listadas em Data/empresas.json, usando as credenciais em Data/empresas_ie.json
    robot.processar_por_empresas()
    
    logger.info("\nProcessamento concluído com sucesso!")

if __name__ == "__main__":
    main()