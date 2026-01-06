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

# Configurações de Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'Data')
EMPRESAS_JSON_PATH = os.path.join(DATA_DIR, 'empresas.siget.json')
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\TUST\SIGETPLUS"
WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'

def sanitize_name(name):
    if not name: return "DESCONHECIDO"
    clean = re.sub(r'[<>:"/\\|?*]', '_', str(name))
    return " ".join(clean.split()).strip()

def carregar_config():
    try:
        if not os.path.exists(EMPRESAS_JSON_PATH):
            return {}
        with open(EMPRESAS_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar JSON: {e}")
        return {}

class SigetRobot:
    def __init__(self):
        self.options = Options()
        self.options.add_argument("--headless=new")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--window-size=1920,1080")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--log-level=3")  # Silencia logs de erro internos do Chrome
        self.options.add_experimental_option("excludeSwitches", ["enable-logging"]) # Remove warnings de devtools
        
        self.service = Service(ChromeDriverManager().install())
        self.driver = None
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        })

    def iniciar_driver(self):
        self.driver = webdriver.Chrome(service=self.service, options=self.options)
        return self.driver

    def login(self, email):
        print(f"\n[LOGIN] Logando: {email}")
        self.driver.get("https://sys.sigetplus.com.br/portal/login")
        wait = WebDriverWait(self.driver, 20)
        email_input = wait.until(EC.presence_of_element_located((By.ID, "email")))
        email_input.send_keys(email)
        self.driver.find_element(By.XPATH, "//button[contains(., 'Entrar')]").click()
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        self.sincronizar_cookies()

    def sincronizar_cookies(self):
        for cookie in self.driver.get_cookies():
            self.session.cookies.set(cookie['name'], cookie['value'])

    def baixar_arquivo_direto(self, url, dest_path, tipo):
        if os.path.exists(dest_path): return True
        try:
            res = self.session.get(url, timeout=30)
            if res.status_code == 200:
                with open(dest_path, 'wb') as f:
                    f.write(res.content)
                print(f"    [OK] {tipo}: {os.path.basename(dest_path)}")
                return True
        except Exception as e:
            print(f"    [ERROR] Erro {tipo}: {e}")
        return False

    def baixar_boleto_otimizado(self, url, dest_path):
        """Baixa HTML via requests e converte para PDF (Ultra Rápido)"""
        if os.path.exists(dest_path): return True
        try:
            res = self.session.get(url, timeout=30)
            if res.status_code == 200:
                config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
                pdfkit.from_string(res.text, dest_path, configuration=config)
                print(f"    [OK] BOLETO: {os.path.basename(dest_path)}")
                return True
        except Exception as e:
            print(f"    [WARN] Falha Boleto Express, tentando Selenium...")
            return False

    def processar_fatura_paralelo(self, dados_fatura):
        """Baixa XML, DANFE e Boletos simultaneamente"""
        dest_folder, info = dados_fatura
        tasks = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            # XML
            if info['xml']:
                tasks.append(executor.submit(self.baixar_arquivo_direto, info['xml'], info['xml_path'], "XML"))
            # DANFE
            if info['danfe']:
                tasks.append(executor.submit(self.baixar_arquivo_direto, info['danfe'], info['danfe_path'], "DANFE"))
            # Boletos
            for i, b_url in enumerate(info['boletos'], 1):
                tasks.append(executor.submit(self.baixar_boleto_otimizado, b_url, info['boleto_paths'][i-1]))
        
    def extrair_dados_tabela(self, ons_name, ons_path):
        """Usa BeautifulSoup para extrair dados sem erros de Stale Element"""
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        rows = soup.select("table.table-striped tbody tr")
        faturas_para_baixar = []
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 10: continue
            
            trans_name = sanitize_name(cols[0].get_text(strip=True))
            num_nf = sanitize_name(cols[1].get_text(strip=True))
            dest_dir = os.path.join(ons_path, trans_name)
            os.makedirs(dest_dir, exist_ok=True)
            
            ts = datetime.now().strftime("%Y%m%d")
            
            links = {
                'xml': None, 'xml_path': os.path.join(dest_dir, f"XML_{ons_name}_{num_nf}_{ts}.xml"),
                'danfe': None, 'danfe_path': os.path.join(dest_dir, f"DANFE_{ons_name}_{num_nf}_{ts}.pdf"),
                'boletos': [], 'boleto_paths': []
            }
            
            # XML e DANFE
            xml_a = cols[9].find("a")
            if xml_a: links['xml'] = urljoin("https://sys.sigetplus.com.br", xml_a.get('href'))
            
            danfe_a = cols[8].find("a")
            if danfe_a: links['danfe'] = urljoin("https://sys.sigetplus.com.br", danfe_a.get('href'))
            
            # Boletos
            for i in range(4, 7): # Índices 0-based para colunas 5, 6, 7
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
        print(f"\n[INFO] Iniciando Agent: {ons_name} (ID: {ons_code})")
        ons_path = os.path.join(BASE_DOWNLOAD_PATH, empresa_nome, str(ons_code))
        os.makedirs(ons_path, exist_ok=True)
        
        self.driver.get(f"https://sys.sigetplus.com.br/portal?agent={ons_code}")
        
        while True:
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "table-striped")))
            self.sincronizar_cookies()
            
            # Coleta todos os links da página
            faturas = self.extrair_dados_tabela(ons_name, ons_path)
            
            # Baixa tudo da página em paralelo
            print(f"  [INFO] Baixando {len(faturas)} faturas da página atual em paralelo...")
            for f in faturas:
                self.processar_fatura_paralelo(f)

            # Próxima Página
            try:
                next_btn = self.driver.find_elements(By.XPATH, "//a[@rel='next']")
                if next_btn:
                    next_btn[0].click()
                    time.sleep(1) # Pequeno buffer para o DOM atualizar
                else: break
            except: break

    def fechar(self):
        if self.driver: self.driver.quit()

def main():
    config_data = carregar_config()
    if not config_data: return
    
    robot = SigetRobot()
    robot.iniciar_driver()
    try:
        for emp_key, info in config_data.items():
            emp_name = emp_key if emp_key.strip() else "AETE"
            email = info.get('email')
            if not email: continue
            
            robot.login(email)
            agentes = info.get('agentes', [])
            if isinstance(agentes, list):
                for d in agentes:
                    for code, name in d.items(): robot.processar_agente(emp_name, code, name)
            elif isinstance(agentes, dict):
                for code, name in agentes.items(): robot.processar_agente(emp_name, code, name)
    finally:
        robot.fechar()
        print("\n[FINISH] Processo Finalizado com Alta Performance!")

if __name__ == "__main__":
    main()