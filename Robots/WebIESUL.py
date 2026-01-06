from robot_base_ie import RobotBaseIE

IE_NOME = "WebIESUL"
IE_URL = "http://faturamento.iesul.com.br"
MAPEAMENTO_CODIGOS = {}

class WebIESULRobot(RobotBaseIE):
    def __init__(self):
        super().__init__(
            nome_ie=IE_NOME,
            url_ie=IE_URL,
            mapeamento_codigos=MAPEAMENTO_CODIGOS
        )

if __name__ == "__main__":
    robot = WebIESULRobot()
    robot.run()
