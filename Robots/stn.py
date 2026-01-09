from alupar_base import AluparBaseRobot

if __name__ == "__main__":
    # STN usa ID 1 e o botão de login é "OK" (diferente das outras que é "Entrar")
    robot = AluparBaseRobot("stn", "1", btn_text="OK")
    robot.run()
