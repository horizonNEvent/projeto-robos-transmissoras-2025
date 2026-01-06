from robot_base_ie import RobotBaseIE

IE_NOME = "WebIEJAGUAR6"
IE_URL = "http://faturamento.iejaguar6.com.br"
MAPEAMENTO_CODIGOS = {}

class WebIEJAGUAR6Robot(RobotBaseIE):
    def __init__(self):
        super().__init__(
            nome_ie=IE_NOME,
            url_ie=IE_URL,
            mapeamento_codigos=MAPEAMENTO_CODIGOS
        )

if __name__ == "__main__":
    robot = WebIEJAGUAR6Robot()
    robot.run()
