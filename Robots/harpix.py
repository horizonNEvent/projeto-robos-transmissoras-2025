import os
import re
import time
import shutil
import datetime
import urllib3
import logging

try:
    import pdfplumber
    from lxml import etree
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    pass

try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= HARPIX ROBOT =================
class HarpixRobot(BaseRobot):
    def __init__(self):
        super().__init__("harpix")
        self.mez_validas = [
            "MEZ 1 ENERGIA",
            "MEZ 2 ENERGIA",
            "MEZ 3 ENERGIA",
            "MEZ 4 ENERGIA",
            "MEZ 5 ENERGIA",
        ]
        self.icon_guids = {
            "BOLETO": "A37AEFD7-1F8D-4153-A39F-84498D81B1B8",
            "XML":    "34D28F8A-100E-4F25-8E0B-88CA10D5B662",
        }
        self.output_dir = self.get_output_path()
        self.driver = None
        self.wait = None

    def setup_driver(self):
        options = Options()
        # Headless mode active by default
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        options.add_experimental_option("prefs", {
            "download.default_directory": self.output_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "safebrowsing.enabled": True,
            "safebrowsing.disable_download_protection": True,
            "plugins.always_open_pdf_externally": True,
        })

        options.add_argument("--disable-features=InsecureDownloadWarnings")
        options.add_argument("--disable-features=DownloadBubble")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 40)

    def sanitize_name(self, name):
        name = re.sub(r'^\d+\s*-\s*', '', name)
        name = re.sub(r'\s*-\s*MATRIZ$', '', name, flags=re.I)
        return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

    def switch_frames(self, frames):
        self.driver.switch_to.default_content()
        for f in frames:
            self.wait.until(EC.frame_to_be_available_and_switch_to_it(f))

    # ================= ORGANIZE FILES HELPER =================
    def normalizar_valor(self, valor):
        if not valor: return None
        return valor.replace(".", "").replace(",", ".").strip()

    def normalizar_data_xml(self, data):
        try:
            return datetime.datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
        except:
            return None

    def extrair_texto_pdf(self, path):
        texto = ""
        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    texto += page.extract_text() or ""
        except Exception as e:
            self.logger.error(f"Erro lendo PDF {path}: {e}")
        return texto.upper()

    def indexar_pdfs(self):
        danfes = []
        boletos = []

        if not os.path.exists(self.output_dir):
            return [], []

        for nome in os.listdir(self.output_dir):
            if not nome.lower().endswith(".pdf"):
                continue

            path = os.path.join(self.output_dir, nome)
            texto = self.extrair_texto_pdf(path)

            chave = re.search(r'\d{44}', texto)
            if "DANFE" in texto and chave:
                danfes.append({"path": path, "chave": chave.group(0)})
                continue

            nf = re.search(r'(\d{3,6})\s*/\s*001', texto)
            valor = re.search(r'\d+,\d{2}', texto)
            datas = re.findall(r'\d{2}/\d{2}/\d{4}', texto)

            if nf or valor or datas:
                boletos.append({
                    "path": path,
                    "nf": nf.group(1) if nf else None,
                    "valor": self.normalizar_valor(valor.group(0)) if valor else None,
                    "datas": datas
                })

        return danfes, boletos

    def ler_xml(self, path):
        ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
        try:
            tree = etree.parse(path)
            return {
                "chave": tree.findtext(".//nfe:chNFe", namespaces=ns),
                "nf": tree.findtext(".//nfe:nNF", namespaces=ns),
                "valor": self.normalizar_valor(tree.findtext(".//nfe:vDup", namespaces=ns)),
                "vencimento": self.normalizar_data_xml(tree.findtext(".//nfe:dVenc", namespaces=ns))
            }
        except Exception as e:
            self.logger.error(f"Erro lendo XML {path}: {e}")
            return {"chave": None, "nf": None, "valor": None, "vencimento": None}

    def organizar_pasta(self, ons_code):
        try:
            arquivos = os.listdir(self.output_dir)
        except FileNotFoundError:
            self.logger.warning(f"Pasta não encontrada: {self.output_dir}")
            return False

        if not any(a.lower().endswith(".xml") for a in arquivos):
            return False

        self.logger.info(f"📂 Organizando arquivos em: {self.output_dir}")
        danfes, boletos = self.indexar_pdfs()

        for nome in arquivos:
            if not nome.lower().endswith(".xml"):
                continue

            xml_path = os.path.join(self.output_dir, nome)
            dados = self.ler_xml(xml_path)

            if not dados["chave"]:
                continue

            pasta_nf = os.path.join(self.output_dir, str(ons_code), dados["chave"])
            os.makedirs(pasta_nf, exist_ok=True)

            try:
                shutil.move(xml_path, os.path.join(pasta_nf, "NF.xml"))
                self.logger.info(f"  [XML] NF {dados['nf']} movido.")
            except Exception as e:
                self.logger.error(f"Erro movendo XML: {e}")

            for d in danfes:
                if d["path"] and d["chave"] == dados["chave"]:
                    try:
                        shutil.move(d["path"], os.path.join(pasta_nf, f"DANFE_NF_{dados['nf']}.pdf"))
                        d["path"] = None
                        self.logger.info(f"    [DANFE] Associado.")
                    except Exception as e:
                        self.logger.error(f"Erro movendo DANFE: {e}")

            for b in boletos:
                if b["path"] is None:
                    continue
                if b["nf"] and b["nf"] != dados["nf"]:
                    continue

                bate_valor = b["valor"] == dados["valor"]
                bate_venc = dados["vencimento"] in (b["datas"] or [])

                if bate_valor or bate_venc:
                    try:
                        shutil.move(b["path"], os.path.join(pasta_nf, f"BOLETO_{dados['nf']}_001.pdf"))
                        b["path"] = None
                        self.logger.info(f"    [BOLETO] Associado.")
                    except Exception as e:
                        self.logger.error(f"Erro movendo Boleto: {e}")

    # ================= LOGIC =================
    def login(self, ons_code):
        self.logger.info(f"Acessando Harpix para código: {ons_code}")
        self.driver.get("https://harpixfat.mezenergia.com/FAT/open.do?sys=FAT")
        try:
            self.switch_frames(["mainform"])
            inp = self.wait.until(EC.presence_of_element_located((By.ID, "WFRInput1051800")))
            inp.clear()
            inp.send_keys(ons_code)
            self.driver.find_element(By.XPATH, "//button[contains(., 'Entrar')]").click()
            time.sleep(8)
            return True
        except Exception as e:
            self.logger.error(f"Erro no login: {e}")
            return False

    def check_announcement_popup(self):
        try:
            popups = self.driver.find_elements(By.CSS_SELECTOR, ".swal2-container")
            if popups and popups[0].is_displayed():
                self.logger.info("📢 Popup de aviso detectado. Fechando...")
                confirm_btn = self.driver.find_elements(By.CSS_SELECTOR, ".swal2-confirm")
                if confirm_btn:
                    confirm_btn[0].click()
                    time.sleep(2)
                    self.logger.info("✅ Popup fechado.")
                    return True
        except:
            pass
        return False

    def acessar_grid(self):
        try:
            self.driver.switch_to.default_content()
            self.switch_frames(["mainsystem", "mainform"])
            self.check_announcement_popup()
            frames = self.driver.find_elements(By.TAG_NAME, "iframe")
            url_frame = next(f.get_attribute("name") for f in frames if f.get_attribute("name").startswith("URLFrame"))
            self.switch_frames(["mainsystem", "mainform", url_frame, "mainform"])
            return url_frame
        except Exception as e:
            self.logger.error(f"Erro ao acessar grid: {e}")
            return None

    def extrair_grid(self):
        try:
            raw = self.driver.execute_script("return typeof data_1051940 !== 'undefined' ? data_1051940 : []")
            faturas = []
            for it in raw:
                try:
                    nome = it["field1051937"]
                    data_str = it["field1051902"]
                    data = datetime.datetime.strptime(data_str, "%d/%m/%Y")
                    if not any(m in nome for m in self.mez_validas): continue
                    faturas.append({"raw": it, "empresa": nome, "data": data})
                except: continue
            if not faturas:
                self.logger.info("Nenhuma fatura encontrada no JS.")
                return []
            maior = max(f["data"] for f in faturas)
            alvo = [f for f in faturas if f["data"].month == maior.month and f["data"].year == maior.year]
            self.logger.info(f"Competência detectada: {maior.strftime('%m/%Y')} | {len(alvo)} faturas.")
            return alvo
        except Exception as e:
            self.logger.error(f"Erro ao extrair grid: {e}")
            return []

    def clicar_download(self, empresa, tipo):
        try:
            guid = self.icon_guids.get(tipo)
            if not guid: return False
            fragmento = self.sanitize_name(empresa).split("ENERGIA")[0] + "ENERGIA"
            xpath = f"//div[contains(text(), '{fragmento}')]/ancestor::tr//img[contains(@src, '{guid}')]"
            btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'})", btn)
            time.sleep(1)
            btn.click()
            
            start_wait = time.time()
            while time.time() - start_wait < 15:
                popups = self.driver.find_elements(By.CSS_SELECTOR, ".swal2-container")
                if popups and popups[0].is_displayed():
                    msg = popups[0].text
                    self.logger.warning(f"⚠️ {tipo} indisponível para {fragmento}: {msg}")
                    confirm_btn = self.driver.find_elements(By.CSS_SELECTOR, ".swal2-confirm")
                    if confirm_btn: confirm_btn[0].click()
                    return False
                toasts = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Aguarde, o PDF')]")
                if not toasts:
                    self.logger.info(f"✅ {tipo} solicitado para {fragmento}")
                    return True
                time.sleep(1)
            return True
        except Exception as e:
            self.logger.error(f"Erro ao clicar download {tipo} para {empresa}: {e}")
            return False

    def run(self):
        target_codes = self.get_agents()
        if not target_codes and self.args.user:
            target_codes = [self.args.user]
        if not target_codes:
            self.logger.error("Nenhum código ONS informado!")
            return

        for ons_code in target_codes:
            ons_code = str(ons_code).strip()
            if not ons_code: continue
            self.logger.info(f"🚀 Iniciando Agente: {ons_code}")
            success = False
            for attempt in range(1, 4):
                if self.driver:
                    try: self.driver.quit()
                    except: pass
                    self.driver = None
                try:
                    self.setup_driver()
                    if not self.login(ons_code): raise Exception("Login falhou")
                    if not self.acessar_grid(): raise Exception("Grid falhou")
                    faturas = self.extrair_grid()
                    if faturas:
                        for f in faturas:
                            for tipo in ["BOLETO", "XML"]:
                                antes = len(os.listdir(self.output_dir))
                                if self.clicar_download(f["empresa"], tipo):
                                    wait_file = time.time()
                                    while time.time() - wait_file < 20:
                                        if len(os.listdir(self.output_dir)) > antes:
                                            self.logger.info(f"  📦 Download detectado para {tipo}")
                                            break
                                        time.sleep(1)
                        time.sleep(5)
                    self.organizar_pasta(ons_code)
                    self.logger.info(f"✅ Sucesso para {ons_code}!")
                    success = True
                    break
                except Exception as e:
                    self.logger.error(f"❌ Erro na tentativa {attempt}: {e}")
                    time.sleep(10)
                finally:
                    if self.driver: self.driver.quit()
                    self.driver = None

if __name__ == "__main__":
    robot = HarpixRobot()
    robot.run()
