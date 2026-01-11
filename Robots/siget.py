import os
import json
import time
import re
import requests
import pdfkit
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor

try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

class SigetRobot(BaseRobot):
    def __init__(self):
        super().__init__("siget")
        self.output_dir = self.get_output_path()
        self.pdf_config = self.get_pdf_config()
        
        # Selenium Config
        self.options = Options()
        self.options.add_argument("--headless=new")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--window-size=1920,1080")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--log-level=3")
        self.options.add_experimental_option("excludeSwitches", ["enable-logging"])
        
        self.service = Service(ChromeDriverManager().install())
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        })

    def iniciar_driver(self):
        if not self.driver:
            self.driver = webdriver.Chrome(service=self.service, options=self.options)
        return self.driver

    def login(self, email):
        self.logger.info(f"Realizando login no SigetPlus para: {email}")
        self.driver.get("https://sys.sigetplus.com.br/portal/login")
        wait = WebDriverWait(self.driver, 20)
        try:
            email_input = wait.until(EC.presence_of_element_located((By.ID, "email")))
            email_input.send_keys(email)
            self.driver.find_element(By.XPATH, "//button[contains(., 'Entrar')]").click()
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            self.sincronizar_cookies()
            return True
        except Exception as e:
            self.logger.error(f"Erro ao realizar login: {e}")
            return False

    def sincronizar_cookies(self):
        for cookie in self.driver.get_cookies():
            self.session.cookies.set(cookie['name'], cookie['value'])

    def sanitize_name(self, name):
        if not name: return "DESCONHECIDO"
        clean = re.sub(r'[<>:"/\\|?*]', '_', str(name))
        return " ".join(clean.split()).strip()

    def baixar_arquivo_direto(self, url, dest_path, tipo):
        if os.path.exists(dest_path): return True
        try:
            res = self.session.get(url, timeout=30)
            if res.status_code == 200:
                with open(dest_path, 'wb') as f:
                    f.write(res.content)
                self.logger.info(f"    [OK] {tipo}: {os.path.basename(dest_path)}")
                return True
        except Exception as e:
            self.logger.error(f"    [ERROR] Erro ao baixar {tipo}: {e}")
        return False

    def baixar_boleto_otimizado(self, url, dest_path):
        if os.path.exists(dest_path): return True
        if not self.pdf_config:
            self.logger.warning(f"Ignorando boleto {os.path.basename(dest_path)} - wkhtmltopdf não disponível")
            return False
        try:
            res = self.session.get(url, timeout=30)
            if res.status_code == 200:
                pdfkit.from_string(res.text, dest_path, configuration=self.pdf_config)
                self.logger.info(f"    [OK] BOLETO: {os.path.basename(dest_path)}")
                return True
        except Exception as e:
            self.logger.warning(f"    [WARN] Falha ao converter boleto: {e}")
            return False

    def processar_fatura_paralelo(self, dados_fatura):
        dest_folder, info = dados_fatura
        with ThreadPoolExecutor(max_workers=5) as executor:
            if info['xml']:
                executor.submit(self.baixar_arquivo_direto, info['xml'], info['xml_path'], "XML")
            if info['danfe']:
                executor.submit(self.baixar_arquivo_direto, info['danfe'], info['danfe_path'], "DANFE")
            for i, b_url in enumerate(info['boletos'], 1):
                executor.submit(self.baixar_boleto_otimizado, b_url, info['boleto_paths'][i-1])

    def extrair_dados_tabela(self, ons_name, ons_path):
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        rows = soup.select("table.table-striped tbody tr")
        faturas_para_baixar = []
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 10: continue
            
            trans_name = self.sanitize_name(cols[0].get_text(strip=True))
            num_nf = self.sanitize_name(cols[1].get_text(strip=True))
            dest_dir = os.path.join(ons_path, trans_name)
            os.makedirs(dest_dir, exist_ok=True)
            
            ts = datetime.now().strftime("%Y%m%d")
            
            links = {
                'xml': None, 'xml_path': os.path.join(dest_dir, f"XML_{ons_name}_{num_nf}_{ts}.xml"),
                'danfe': None, 'danfe_path': os.path.join(dest_dir, f"DANFE_{ons_name}_{num_nf}_{ts}.pdf"),
                'boletos': [], 'boleto_paths': []
            }
            
            xml_a = cols[9].find("a")
            if xml_a: links['xml'] = urljoin("https://sys.sigetplus.com.br", xml_a.get('href'))
            
            danfe_a = cols[8].find("a")
            if danfe_a: links['danfe'] = urljoin("https://sys.sigetplus.com.br", danfe_a.get('href'))
            
            for i in range(4, 7):
                try:
                    b_a = cols[i].find("a")
                    if b_a and 'billet' in b_a.get('href', ''):
                        b_url = urljoin("https://sys.sigetplus.com.br", b_a.get('href'))
                        links['boletos'].append(b_url)
                        links['boleto_paths'].append(os.path.join(dest_dir, f"BOLETO_{ons_name}_{num_nf}_{len(links['boletos'])}_{ts}.pdf"))
                except: continue
            
            faturas_para_baixar.append((dest_dir, links))
        return faturas_para_baixar

    def processar_agente(self, empresa_nome, ons_code, ons_name):
        self.logger.info(f"Processando Agente: {ons_name} (ID: {ons_code})")
        # Criar pasta no padrão: downloads/siget/Empresa/ONS/Transmissora
        ons_path = os.path.join(self.output_dir, empresa_nome, str(ons_code))
        os.makedirs(ons_path, exist_ok=True)
        
        self.driver.get(f"https://sys.sigetplus.com.br/portal?agent={ons_code}")
        
        while True:
            try:
                WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "table-striped")))
                self.sincronizar_cookies()
                faturas = self.extrair_dados_tabela(ons_name, ons_path)
                
                if faturas:
                    self.logger.info(f"  Baixando {len(faturas)} faturas da página atual...")
                    for f in faturas:
                        self.processar_fatura_paralelo(f)
                else:
                    self.logger.info("  Nenhuma fatura encontrada nesta página.")

                # Paginação
                next_btn = self.driver.find_elements(By.XPATH, "//a[@rel='next']")
                if next_btn:
                    next_btn[0].click()
                    time.sleep(1)
                else:
                    break
            except Exception as e:
                self.logger.error(f"Erro ao processar página de faturas: {e}")
                break

    def run(self):
        email = self.args.user
        empresa_label = self.args.empresa or "PADRAO"
        agentes_str = self.args.agente
        
        if not email:
            self.logger.error("E-mail não fornecido. O robô precisa de um usuário para logar.")
            return

        self.iniciar_driver()
        try:
            if self.login(email):
                # Se passou agentes específicos, usa eles. Se não, tenta descobrir? 
                # (No Siget o padrão é receber a lista de quem processar)
                lista_agentes = self.get_agents()
                if not lista_agentes:
                    self.logger.warning("Nenhum agente fornecido para processamento.")
                    return

                for ons_code in lista_agentes:
                    # Como o label amigável (nome do agente) não vem no argumento, usamos o próprio código como nome
                    self.processar_agente(empresa_label, ons_code, ons_code)
        finally:
            if self.driver:
                self.driver.quit()
            self.logger.info("Processo Finalizado!")

if __name__ == "__main__":
    robot = SigetRobot()
    robot.run()