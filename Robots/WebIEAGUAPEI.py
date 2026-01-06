from robot_base_ie import RobotBaseIE

IE_NOME = "WebIEAGUAPEI"
IE_URL = "http://faturamento.ieaguapei.com.br"
MAPEAMENTO_CODIGOS = {}

class WebIEAGUAPEIRobot(RobotBaseIE):
    def __init__(self):
        super().__init__(
            nome_ie=IE_NOME,
            url_ie=IE_URL,
            mapeamento_codigos=MAPEAMENTO_CODIGOS
        )

if __name__ == "__main__":
    robot = WebIEAGUAPEIRobot()
    robot.run()
