from robot_base_ie import RobotBaseIE

IE_NOME = "WebIEIVAI"
IE_URL = "http://faturamento.ieivai.com.br"
MAPEAMENTO_CODIGOS = {}

class WebIEIVAIRobot(RobotBaseIE):
    def __init__(self):
        super().__init__(
            nome_ie=IE_NOME,
            url_ie=IE_URL,
            mapeamento_codigos=MAPEAMENTO_CODIGOS
        )

if __name__ == "__main__":
    robot = WebIEIVAIRobot()
    robot.run()
