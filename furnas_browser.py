import os
import time
from playwright.sync_api import sync_playwright

class FurnasBrowserDownloader:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.base_url = "https://portaldocliente.eletrobras.com/sap/bc/webdynpro/sap/zwda_portalclientes?sap-client=130&sap-theme=sap_bluecrystal#"

    def run(self):
        with sync_playwright() as p:
            # 1. Abrir navegador
            browser = p.chromium.launch(headless=False) # Headless=False para podermos ver se precisar
            page = browser.new_page()
            
            print(f"Navegando para o portal Furnas...")
            page.goto(self.base_url)
            
            # 2. Preencher Login
            print(f"Preenchendo credenciais para {self.username}...")
            # O SAP usa IDs como WD2C e WD32, mas vamos usar seletores robustos
            page.wait_for_selector("input[name='WD2C']")
            page.fill("input[name='WD2C']", self.username)
            page.fill("input[name='WD32']", self.password)
            
            # 3. Clicar em Entrar
            print("Clicando em Entrar...")
            page.click("text=Entrar")
            
            # 4. Esperar o Dashboard
            try:
                # Esperar por algo que indique que logou (ex: as abas das transmissoras)
                page.wait_for_selector("text=FURNAS", timeout=20000)
                print("Login realizado com sucesso via Navegador!")
                
                # Tirar print do sucesso
                page.screenshot(path="furnas_success.png")
                
                # Aqui entra a lógica de navegar nas abas e baixar
                # Vou implementar o clique na primeira aba como teste
                # ...
                
            except Exception as e:
                print(f"Erro ao logar ou encontrar dashboard: {e}")
                page.screenshot(path="furnas_error_dashboard.png")
            
            time.sleep(5)
            browser.close()

if __name__ == "__main__":
    downloader = FurnasBrowserDownloader("fatbol_2wecobank@vbasystems.com.br", "12345678")
    downloader.run()
