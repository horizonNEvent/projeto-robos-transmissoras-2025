from alupar_base import AluparBaseRobot

if __name__ == "__main__":
    # TECP usa ID 56 (Mesmo do TCPE)
    robot = AluparBaseRobot("tecp", "56")
    robot.run()
