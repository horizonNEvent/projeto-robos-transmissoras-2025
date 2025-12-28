import os
import time
import json
import re
import datetime
import base64
import requests
from urllib.parse import quote
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configurações
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\Tust\ENGIE"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data")
EMPRESAS_JSON_PATH = os.path.join(DATA_DIR, "empresas.json")

def sanitize_name(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

class EngieRobot:
    def __init__(self, ons_code, ons_name):
        self.ons_code = ons_code
        self.ons_name = ons_name
        self.output_path = os.path.join(BASE_DOWNLOAD_PATH, self.ons_name)
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path, exist_ok=True)
        
        self.session = requests.Session()
        self.aura_context = {}
        self.fwuid = ""
        self.request_id = 1
        self.action_id = 100 # Iniciar contador alto para evitar colisões

    def initialize_session(self):
        """Usa Selenium para pegar cookies e contexto Aura atualizados."""
        print("    [AUTO] Inicializando sessão técnica via Selenium...")
        options = Options()
        options.add_argument("--headless")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        try:
            driver.get("https://engiebrasil.my.site.com/portaltransmissora/s/")
            time.sleep(10)
            
            # Capturar o contexto do objeto global window.aura
            raw_context = driver.execute_script("return window.aura.getContext();")
            self.fwuid = raw_context.get('Nr')
            self.aura_context = {
                "mode": "PROD",
                "fwuid": self.fwuid,
                "app": "siteforce:communityApp",
                "loaded": raw_context.get('loaded', {}),
                "dn": [],
                "globals": {},
                "uad": False
            }
            
            # Sincronizar cookies
            for cookie in driver.get_cookies():
                self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
                
            print(f"    [OK] fwuid capturado: {self.fwuid[:10]}...")
            return True
        finally:
            driver.quit()

    def call_aura(self, descriptor, params, extra_key=""):
        url = f"https://engiebrasil.my.site.com/portaltransmissora/s/sfsites/aura?r={self.request_id}"
        if extra_key:
            url += f"&{extra_key}=1"
        
        message = {
            "actions": [
                {
                    "id": f"{self.action_id};a",
                    "descriptor": descriptor,
                    "callingDescriptor": "markup://c:PortaltransmissoraTab",
                    "params": params
                }
            ]
        }
        
        payload = {
            "message": json.dumps(message),
            "aura.context": json.dumps(self.aura_context),
            "aura.pageURI": "/portaltransmissora/s/",
            "aura.token": "null"
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://engiebrasil.my.site.com/portaltransmissora/s/"
        }
        
        # Encodar payload manualmente para manter a ordem se necessário (algumas APIs Salesforce são sensíveis)
        data_str = "&".join([f"{k}={quote(v)}" for k, v in payload.items()])
        
        try:
            r = self.session.post(url, data=data_str, headers=headers)
            self.request_id += 1
            self.action_id += 1
            
            if r.status_code == 200:
                resp_json = r.json()
                # Verificar se o framework foi atualizado (erro comum no Salesforce)
                if "Framework has been updated" in r.text:
                    print("    [AVISO] Framework atualizado no servidor. Tentando extrair novo fwuid...")
                    # Aqui poderíamos reinicializar, mas por ora vamos falhar
                    return None
                
                actions = resp_json.get('actions', [])
                if actions and actions[0].get('state') == 'SUCCESS':
                    return actions[0].get('returnValue')
                else:
                    print(f"    [ERRO] API devolveu erro: {actions[0].get('error') if actions else 'Sem corpo'}")
            else:
                print(f"    [ERRO] HTTP {r.status_code}")
        except Exception as e:
            print(f"    [ERRO] na requisição: {e}")
        return None

    def processar(self):
        print(f"\n>>> [ENGIE] ONS: {self.ons_code} ({self.ons_name})")
        if not self.initialize_session(): return
        
        # Competência (1º do mês atual)
        data_busca = datetime.date.today().replace(day=1).strftime("%Y-%m-%d")
        
        print(f"    - Buscando faturas (Data: {data_busca})...")
        faturas = self.call_aura(
            "apex://PortalTransmissoraTabLController/ACTION$getInvoiceList",
            {"ONSCode": str(self.ons_code), "selectDate": data_busca},
            "other.PortalTransmissoraTabL.getInvoiceList"
        )
        
        if not faturas:
            print(f"    [AVISO] Nenhuma fatura encontrada para {self.ons_code}.")
            return

        print(f"    [OK] {len(faturas)} faturas recebidas.")

        for f in faturas:
            empresa = f.get('BillFromName__c', 'Empresa')
            invoice_key = f.get('InvoiceKey__c')
            instalment_id = f.get('FirstInstalmentId__c')
            
            print(f"\n      🚀 {empresa}")
            
            # Boleto
            if instalment_id:
                self.baixar(invoice_key, "BOLETO", "apex://PortalTransmissoraTabLController/ACTION$downloadBillet", 
                           {"invoiceKey": invoice_key, "instalmentId": instalment_id}, "other.PortalTransmissoraTabL.downloadBillet", empresa)
            
            # DANFE
            self.baixar(invoice_key, "DANFE", "apex://PortalTransmissoraTabLController/ACTION$downloadInvoicePDF", 
                       {"NFe": invoice_key}, "other.PortalTransmissoraTabL.downloadInvoicePDF", empresa)
            
            # XML
            self.baixar(invoice_key, "XML", "apex://PortalTransmissoraTabLController/ACTION$downloadInvoiceXML", 
                       {"NFe": invoice_key}, "other.PortalTransmissoraTabL.downloadInvoiceXML", empresa)

    def baixar(self, key, tipo, descriptor, params, extra_key, trans_name):
        print(f"        -> {tipo}...")
        res_b64 = self.call_aura(descriptor, params, extra_key)
        
        if res_b64:
            safe_trans = sanitize_name(trans_name)
            # Criar pasta da transmissora
            path_trans = os.path.join(self.output_path, safe_trans)
            if not os.path.exists(path_trans):
                os.makedirs(path_trans, exist_ok=True)
                
            ext = ".xml" if tipo == "XML" else ".pdf"
            filename = f"{tipo}_{safe_trans}_{self.ons_code}_{datetime.datetime.now().strftime('%Y%m%d')}{ext}"
            target = os.path.join(path_trans, filename)
            
            try:
                if res_b64.startswith('PD94bWw') or res_b64.startswith('JVBER'):
                    content = base64.b64decode(res_b64)
                else:
                    content = res_b64.encode('utf-8')
                    
                with open(target, 'wb') as file:
                    file.write(content)
                print(f"           [OK] Salvo em: {safe_trans}")
            except:
                print(f"           [ERRO] ao salvar {tipo}")
        else:
            print(f"           [AVISO] {tipo} pendente/erro.")

if __name__ == "__main__":
    with open(EMPRESAS_JSON_PATH, 'r') as f:
        config = json.load(f)
    
    for ons_code, ons_name in config.get("AETE", {}).items():
        bot = EngieRobot(ons_code, ons_name)
        bot.processar()
