import os
import json
import time
import requests
import urllib3
import logging
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuração de LOG
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("EQUATORIAL")

BASE_DIR_DOWNLOAD = r"C:\Users\Bruno\Downloads\TUST\EQUATORIAL"

def carregar_dados_equatorial():
    """Carrega dados do Data/empresas.equatorial.json"""
    try:
        arquivo_json = os.path.join(os.path.dirname(__file__), 'Data', 'empresas.equatorial.json')
        if not os.path.exists(arquivo_json):
            logger.error(f"Arquivo não encontrado: {arquivo_json}")
            return {}
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar JSON: {e}")
        return {}

def setup_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--headless=False") # Mude para False para ver o navegador
    
    prefs = {
        "plugins.always_open_pdf_externally": True,
        "download.prompt_for_download": False,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=options)
    return driver

class EquatorialRobot:
    def __init__(self):
        self.url = "https://www.equatorial-t.com.br/segunda-via-transmissao/"
        self.driver = setup_driver()
        self.wait = WebDriverWait(self.driver, 15)

    def close_popups(self):
        """Fecha modais e avisos de cookies"""
        try:
            cookie_btn = WebDriverWait(self.driver, 2).until(
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            )
            self.driver.execute_script("arguments[0].click();", cookie_btn)
        except: pass

        try:
            modal_close = WebDriverWait(self.driver, 2).until(
                EC.element_to_be_clickable((By.ID, "gmz-modal-close"))
            )
            self.driver.execute_script("arguments[0].click();", modal_close)
        except: pass

    def download_file(self, url, dest_folder, filename):
        """Executa download usando a sessão do navegador"""
        try:
            session = requests.Session()
            for cookie in self.driver.get_cookies():
                session.cookies.set(cookie['name'], cookie['value'])
            
            headers = {"User-Agent": self.driver.execute_script("return navigator.userAgent;")}
            response = session.get(url, headers=headers, stream=True, verify=False)
            response.raise_for_status()
            
            filepath = os.path.join(dest_folder, filename)
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"✅ Salvo: {filename}")
            return True
        except Exception as e:
            logger.error(f"Erro no download {filename}: {e}")
            return False

    def process_spe(self, empresa_nome, cnpj, codigo_ons, spe):
        """Processa uma SPE específica (SP01, SP02, etc)"""
        try:
            logger.info(f"[{empresa_nome}] ONS {codigo_ons} | Testando SPE: {spe}")
            
            self.driver.get(self.url)
            self.close_popups()

            # Preenchimento do Login
            try:
                # Aguarda os inputs aparecerem
                self.wait.until(EC.presence_of_element_located((By.ID, "user_spe")))
                
                inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
                if len(inputs) < 2:
                    logger.warning(f"[{spe}] Inputs de login não encontrados.")
                    return

                inputs[0].clear()
                inputs[0].send_keys(cnpj)
                inputs[1].clear()
                inputs[1].send_keys(codigo_ons)
                
                spe_input = self.driver.find_element(By.ID, "user_spe")
                spe_input.clear()
                spe_input.send_keys(spe)
                spe_input.send_keys(Keys.ENTER)
                
                time.sleep(3)
                self.close_popups()

                # Busca faturas na tabela
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                latest_date = None
                latest_row = None
                
                for row in rows:
                    cols = row.find_all(By.TAG_NAME, "td") if hasattr(row, 'find_all') else row.find_elements(By.TAG_NAME, "td")
                    if len(cols) < 7: continue
                    
                    # Filtro 1: Apenas "Em aberto"
                    status = cols[0].text.strip().lower()
                    if "aberto" not in status:
                        continue
                    
                    # Filtro 2: Encontrar a data mais recente
                    try:
                        mes = int(cols[3].text.strip())
                        ano = int(cols[4].text.strip())
                        current_date = (ano, mes)
                        
                        if latest_date is None or current_date > latest_date:
                            latest_date = current_date
                            latest_row = row
                    except:
                        continue

                if not latest_row:
                    logger.info(f"[{spe}] Nenhuma fatura 'Em aberto' encontrada.")
                    return

                # Processa a fatura mais recente encontrada
                cols = latest_row.find_elements(By.TAG_NAME, "td")
                ano_fatura, mes_fatura = latest_date
                
                # Identificador para a pasta (NF_AnoMes)
                id_nf = f"{ano_fatura}{mes_fatura:02d}"
                
                # Caminho Padronizado: EQUATORIAL / [Empresa] / [ONS] / [SPE] / NF_[AnoMes]
                # Adicionado a subpasta da SPE para separar as transmissoras
                base_path = Path(BASE_DIR_DOWNLOAD) / empresa_nome / str(codigo_ons) / spe / f"NF_{id_nf}"
                base_path.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Links de download (Colunas 5 e 6)
                xml_links = cols[5].find_elements(By.TAG_NAME, "a")
                pdf_links = cols[6].find_elements(By.TAG_NAME, "a")

                if xml_links:
                    self.download_file(xml_links[0].get_attribute("href"), base_path, f"NFe_EQUATORIAL_{spe}_{timestamp}.xml")
                
                if pdf_links:
                    self.download_file(pdf_links[0].get_attribute("href"), base_path, f"DANFE_EQUATORIAL_{spe}_{timestamp}.pdf")

            except Exception as e:
                logger.error(f"Erro no fluxo da SPE {spe}: {e}")

            # Logout explícito para permitir o próximo loop
            self.driver.get("https://www.equatorial-t.com.br/login-cliente?action=logout")
            time.sleep(2)

        except Exception as e:
            logger.error(f"Erro geral na SPE {spe}: {e}")

    def run(self):
        dados = carregar_dados_equatorial()
        if not dados: return

        spes_para_testar = ["SP01", "SP02", "SP03", "SP04", "SP05", "SP06", "SP08"]
        
        for empresa_nome, agentes in dados.items():
            logger.info(f"\n=== Processando Empresa: {empresa_nome} ===")
            for codigo_ons, info in agentes.items():
                cnpj = info.get("cnpj")
                
                for spe in spes_para_testar:
                    self.process_spe(empresa_nome, cnpj, codigo_ons, spe)
            
        logger.info("Processamento finalizado.")
        self.driver.quit()

if __name__ == "__main__":
    robot = EquatorialRobot()
    robot.run()