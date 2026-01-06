from robot_base_ie import RobotBaseIE

IE_NOME = "WebIEJAGUAR8"
IE_URL = "http://faturamento.iejaguar8.com.br"
MAPEAMENTO_CODIGOS = {}

class WebIEJAGUAR8Robot(RobotBaseIE):
    def __init__(self):
        super().__init__(
            nome_ie=IE_NOME,
            url_ie=IE_URL,
            mapeamento_codigos=MAPEAMENTO_CODIGOS
        )

if __name__ == "__main__":
    robot = WebIEJAGUAR8Robot()
    robot.run()
