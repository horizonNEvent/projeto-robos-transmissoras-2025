import json
import os
import time
import datetime
import traceback
import shutil
import requests
import urllib3
import sys
import re

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

# Desabilita avisos de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
if sys.stdout.encoding != 'UTF-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# Configurações de Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'Data')
EMPRESAS_JSON_PATH = os.path.join(DATA_DIR, 'empresas.json')
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\TUST\HARPIX"

ICON_GUIDS = {
    "BOLETO": "A37AEFD7-1F8D-4153-A39F-84498D81B1B8",
    "XML": "34D28F8A-100E-4F25-8E0B-88CA10D5B662",
    "DANFE": "54E749DF-92C8-49E0-8F13-03625F00CDEC"
}

def sanitize_name(name):
    if not name: return "DESCONHECIDO"
    name = re.sub(r'^\d+\s*-\s*', '', name)
    name = re.sub(r'\s*-\s*MATRIZ$', '', name, flags=re.IGNORECASE)
    clean = re.sub(r'[<>:"/\\|?*]', '_', name)
    return " ".join(clean.split()).strip()

def carregar_empresas():
    try:
        with open(EMPRESAS_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

def configurar_chrome(pasta_download):
    chrome_options = Options()
    # chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    chrome_options.add_experimental_option('prefs', {
        'download.default_directory': pasta_download,
        'plugins.always_open_pdf_externally': True
    })
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

class HarpixRobot:
    def __init__(self, empresa_nome, ons_code, ons_name):
        self.empresa_nome = empresa_nome
        self.ons_code = ons_code
        self.ons_name = ons_name
        self.output_path = os.path.join(BASE_DOWNLOAD_PATH, empresa_nome, str(ons_code))
        os.makedirs(self.output_path, exist_ok=True)
        self.driver = configurar_chrome(self.output_path)
        self.wait = WebDriverWait(self.driver, 40)

    def capturar_url(self, pattern):
        try:
            logs = self.driver.get_log('performance')
            for entry in logs:
                msg = json.loads(entry['message'])['message']
                if msg.get('method') == 'Network.requestWillBeSent':
                    url = msg.get('params', {}).get('request', {}).get('url', '')
                    if re.search(pattern, url): return url
        except: pass
        return None

    def baixar(self, trans_text, tipo_doc, url_frame):
        try:
            self.driver.switch_to.default_content()
            for f in ["mainsystem", "mainform", url_frame, "mainform"]:
                self.wait.until(EC.frame_to_be_available_and_switch_to_it(f))

            guid = ICON_GUIDS[tipo_doc]
            
            # Divide o nome da transmissora para pegar a parte principal (ex: "MEZ 3 ENERGIA")
            # Isso torna a busca do texto mais flexível
            fragmento = re.sub(r'^\d+\s*-\s*', '', trans_text).split("ENERGIA")[0] + "ENERGIA"
            
            # XPath: Encontra a div que contém o texto da transmissora
            txt_xpath = f"//div[contains(text(), '{fragmento}')]"
            
            # Localiza o texto e rola até ele
            try:
                txt_el = self.wait.until(EC.presence_of_element_located((By.ID, "grdFaturas"))) # Wrapper do grid
                # Na verdade, buscamos o texto dentro do grid
                txt_el = self.driver.find_element(By.XPATH, txt_xpath)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", txt_el)
                time.sleep(1)
            except: pass

            # Agora busca o ícone na linha (TR ou pai comum)
            xpath = f"//div[contains(text(), '{fragmento}')]/ancestor::tr//img[contains(@src, '{guid}')]"
            
            # Se falhar o TR (Maker às vezes usa divs), busca no container próximo
            if not self.driver.find_elements(By.XPATH, xpath):
                xpath = f"//div[contains(text(), '{fragmento}')]/parent::td/parent::tr//img[contains(@src, '{guid}')]"

            btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            
            self.driver.get_log('performance') # Limpa logs
            btn.click()
            
            # SweetAlert
            time.sleep(1.5)
            if self.driver.find_elements(By.CSS_SELECTOR, ".swal2-confirm"):
                print(f"      ⚠️ {tipo_doc} indisponível para {fragmento}.")
                self.driver.execute_script("document.querySelector('.swal2-confirm').click();")
                return

            # Interceptação
            try:
                start = time.time()
                pattern = r'openreport\.aspx|type=PDF|\.xml'
                while time.time() - start < 15:
                    final_url = self.capturar_url(pattern)
                    if final_url:
                        ext = ".xml" if tipo_doc == "XML" else ".pdf"
                        safe_trans = sanitize_name(trans_text)
                        filename = f"{tipo_doc}_{safe_trans}_{self.ons_name}_{datetime.datetime.now().strftime('%Y%m%d')}{ext}"
                        
                        r = requests.get(final_url, cookies={c['name']: c['value'] for c in self.driver.get_cookies()}, verify=False)
                        if r.status_code == 200:
                            with open(os.path.join(self.output_path, filename), 'wb') as f:
                                f.write(r.content)
                            print(f"    ✓ {tipo_doc} salvo.")
                            break
                    time.sleep(0.5)
                else:
                    print(f"    ⚠️ Falha capturar URL de {tipo_doc}.")
            finally:
                # Limpeza de janelas: Fecha qualquer janela que não seja a principal
                if len(self.driver.window_handles) > 1:
                    main_window = self.driver.window_handles[0]
                    for handle in self.driver.window_handles:
                        if handle != main_window:
                            try:
                                self.driver.switch_to.window(handle)
                                self.driver.close()
                            except: pass
                    self.driver.switch_to.window(main_window)
                    # Volta para os frames internos após fechar as janelas
                    for f in ["mainsystem", "mainform", url_frame, "mainform"]:
                        self.wait.until(EC.frame_to_be_available_and_switch_to_it(f))

        except Exception as e:
            print(f"    ❌ Erro {tipo_doc} ({trans_text}): {e}")

    def processar(self):
        print(f"\n>>> [HARPIX] ONS: {self.ons_name}")
        try:
            self.driver.get("https://harpixfat.mezenergia.com/FAT/open.do?sys=FAT")
            self.wait.until(EC.frame_to_be_available_and_switch_to_it("mainform"))
            self.wait.until(EC.presence_of_element_located((By.ID, "WFRInput1051800"))).send_keys(self.ons_code)
            self.driver.find_element(By.XPATH, "//button[contains(., 'Entrar')]").click()
            time.sleep(8)
            
            self.driver.switch_to.default_content()
            self.wait.until(EC.frame_to_be_available_and_switch_to_it("mainsystem"))
            self.wait.until(EC.frame_to_be_available_and_switch_to_it("mainform"))
            frames = self.driver.find_elements(By.TAG_NAME, "iframe")
            url_frame = next(f.get_attribute('name') for f in frames if f.get_attribute('name').startswith('URLFrame'))
            
            self.wait.until(EC.frame_to_be_available_and_switch_to_it(url_frame))
            self.wait.until(EC.frame_to_be_available_and_switch_to_it("mainform"))

            # Extração
            raw = self.driver.execute_script("return typeof data_1051940 !== 'undefined' ? data_1051940 : []")
            if not raw: time.sleep(5); raw = self.driver.execute_script("return data_1051940")

            faturas = []
            for it in raw:
                try:
                    faturas.append({
                        'trans_raw': it['field1051937'],
                        'data': datetime.datetime.strptime(it['field1051902'], "%d/%m/%Y")
                    })
                except: continue

            if not faturas: return
            maior_dt = max(f['data'] for f in faturas)
            alvo = [f for f in faturas if f['data'].month == maior_dt.month and f['data'].year == maior_dt.year]
            
            print(f"    📅 Competência: {maior_dt.strftime('%m/%Y')} | {len(alvo)} faturas.")

            for f in alvo:
                print(f"\n      🚀 Empresa: {f['trans_raw']}")
                for tipo in ["BOLETO", "XML", "DANFE"]:
                    self.baixar(f['trans_raw'], tipo, url_frame)

        except Exception as e:
            print(f"    ❌ Erro: {e}")
        finally:
            self.driver.quit()

def main():
    cfg = carregar_empresas()
    for emp, ons_dict in cfg.items():
        for code, name in ons_dict.items():
            HarpixRobot(emp, code, name).processar()

if __name__ == "__main__":
    main()