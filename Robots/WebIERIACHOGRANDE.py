from robot_base_ie import RobotBaseIE

IE_NOME = "WebIERIACHOGRANDE"
IE_URL = "https://faturamento.ieriachogrande.com.br"
MAPEAMENTO_CODIGOS = {
    # Mapeamentos específicos se precisarem ser fixos, senão usa o empresas.json
}

class WebIERIACHOGRANDERobot(RobotBaseIE):
    def __init__(self):
        super().__init__(
            nome_ie=IE_NOME,
            url_ie=IE_URL,
            mapeamento_codigos=MAPEAMENTO_CODIGOS
        )

if __name__ == "__main__":
    robot = WebIERIACHOGRANDERobot()
    robot.run()
