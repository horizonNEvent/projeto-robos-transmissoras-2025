import os
import time
import json
import requests
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

# Import BaseRobot
try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

class MGERobot(BaseRobot):
    """
    Robô para Grupo MGE (Websiteseguro).
    Login via Código ONS (sem senha).
    """

    def __init__(self):
        super().__init__("mge")
        self.url = "https://ssl5501.websiteseguro.com/transenergia/fatura/index.php"
        self.transmissoras = [
            "TRANSENERGIA RENOVÁVEL S.A.",
            "MGE TRANSMISSAO SA",
            "GOIAS TRANSMISSAO SA",
            "TRANSENERGIA SÃO PAULO S.A."
        ]
        self.session = requests.Session()

    def setup_driver(self, output_dir):
        chrome_options = Options()
        prefs = {
            "download.default_directory": output_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "plugins.always_open_pdf_externally": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
         # Modo headless recomendado para servidor
        chrome_options.add_argument("--headless") 
        chrome_options.add_argument("--window-size=1920,1080")

        return webdriver.Chrome(options=chrome_options)

    def filtrar_por_mes(self, faturas, mes, ano=None):
        """Filtra faturas por mês de emissão"""
        filtradas = []
        for f in faturas:
            try:
                dt_emissao = datetime.datetime.strptime(f['emissao'], '%d/%m/%Y')
                if dt_emissao.month == mes:
                    if ano is None or dt_emissao.year == ano:
                        filtradas.append(f)
            except: continue
        return filtradas

    def run(self):
        agente_ons = self.args.agente
        
        # Se não vier agente, tenta fallback para lista completa (lógica do script original)
        # Mas como a ordem é priorizar o front, se não vier agente, vamos erro.
        # Ou podemos ler o empresas.json se quisermos manter a func completa.
        # Vamos focar no caso Agente Individual por enquanto.
        
        if not agente_ons:
            self.logger.error("Código ONS (Agente) é obrigatório para este robô.")
            return

        competencia_str = self.args.competencia
        target_mes = datetime.datetime.now().month
        target_ano = datetime.datetime.now().year
        
        if competencia_str and len(competencia_str) == 6:
            target_ano = int(competencia_str[:4])
            target_mes = int(competencia_str[4:6])

        self.logger.info(f"Iniciando MGE para Agente: {agente_ons}, Competência: {target_mes}/{target_ano}")

        output_dir = self.get_output_path()
        # Subpasta para o Agente para ficar organizado
        # output_dir = os.path.join(output_dir, str(agente_ons))
        os.makedirs(output_dir, exist_ok=True)

        driver = self.setup_driver(output_dir)
        wait = WebDriverWait(driver, 30)

        try:
            # 1. Acesso
            self.logger.info("Acessando site...")
            driver.get(self.url)
            
            # 2. Login
            self.logger.info(f"Logando com ONS {agente_ons}...")
            wait.until(EC.presence_of_element_located((By.ID, "codigoONS"))).send_keys(agente_ons)
            wait.until(EC.element_to_be_clickable((By.ID, "btnAcessar"))).click()
            time.sleep(5) # Aumentado de 3 para 5s

            # 3. Validar Acesso
            if "index.php" in driver.current_url:
                # Tenta capturar mensagem de erro
                error_msg = "Desconhecido"
                try: 
                    # Tenta pegar alerta do Bootstrap ou similar
                    alerts = driver.find_elements(By.CLASS_NAME, "alert-danger")
                    if alerts:
                        error_msg = alerts[0].text
                    else:
                        # Tenta pegar qualquer texto vermelho
                        spans = driver.find_elements(By.XPATH, "//*[contains(@style, 'color: red') or contains(@class, 'error')]")
                        if spans:
                            error_msg = spans[0].text
                except: pass

                self.logger.error(f"Falha ao logar. URL: {driver.current_url} | Erro detectado: {error_msg}")
                # Debug: Salvar HTML para analise se necessario (print no log)
                # self.logger.info(f"HTML: {driver.page_source[:500]}")
                return

            self.logger.info("Login OK. Extraindo faturas...")
            
            # 4. Extrair Dados
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table")))
            linhas = driver.find_elements(By.CSS_SELECTOR, "table.table tbody tr")
            
            faturas = []
            for col in linhas:
                cols = col.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 6:
                    dados = {
                        'estabelecimento': cols[0].text.strip(),
                        'emissao': cols[1].text.strip(),
                        'numero': cols[3].text.strip(),
                        'links': {}
                    }
                    links = col.find_elements(By.TAG_NAME, "a")
                    for lnk in links:
                        u = lnk.get_attribute("href")
                        t = lnk.text
                        if "XML" in t: dados['links']['xml'] = u
                        elif "DANFE" in t: dados['links']['danfe'] = u
                        elif "Boleto" in t: dados['links']['boleto'] = u
                    faturas.append(dados)
            
            # 5. Filtrar Competência
            if competencia_str:
                # Se usuário pediu data específica, filtra por ela
                faturas_alvo = self.filtrar_por_mes(faturas, target_mes, target_ano)
                self.logger.info(f"Filtrando por {target_mes}/{target_ano}. Encontradas: {len(faturas_alvo)}")
            else:
                # LÓGICA AUTOMÁTICA (Mais recente)
                # Encontrar a data de emissão mais recente na lista
                if not faturas:
                    faturas_alvo = []
                else:
                    datas = []
                    for f in faturas:
                        try:
                            dt = datetime.datetime.strptime(f['emissao'], '%d/%m/%Y')
                            datas.append(dt)
                        except: pass
                    
                    if datas:
                        maior_data = max(datas)
                        mes_recente = maior_data.month
                        ano_recente = maior_data.year
                        self.logger.info(f"Nenhuma competência informada. Usando mês mais recente encontrado: {mes_recente}/{ano_recente}")
                        faturas_alvo = self.filtrar_por_mes(faturas, mes_recente, ano_recente)
                    else:
                        faturas_alvo = []

            if not faturas_alvo:
                 self.logger.warning(f"Nenhuma fatura encontrada (Filtro: {competencia_str if competencia_str else 'Mais Recente'}).") 
            
            self.logger.info(f"Processando {len(faturas_alvo)} faturas...")

            # 6. Baixar
            # Configura requests com cookies do selenium
            selenium_cookies = driver.get_cookies()
            for cookie in selenium_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': driver.current_url
            }

            for fat in faturas_alvo:
                nome_empresa = fat['estabelecimento'].replace(" ", "_")
                num_nota = fat['numero']
                
                # Cria subpasta com nome da transmissora (como no script original)
                # ou tudo na raiz do agente? O original separa por Transmissora.
                # Vamos simplificar e jogar na pasta do ONS mas com prefixo claro?
                # Ou criar pasta Transmissora.
                
                pasta_final = os.path.join(output_dir, nome_empresa)
                os.makedirs(pasta_final, exist_ok=True)
                
                # Baixa XML
                if 'xml' in fat['links']:
                    nome = f"NFe_{nome_empresa}_{num_nota}.xml"
                    self._baixar_arquivo(fat['links']['xml'], os.path.join(pasta_final, nome), headers)
                
                # Baixa DANFE
                if 'danfe' in fat['links']:
                    nome = f"DANFE_{nome_empresa}_{num_nota}.pdf"
                    self._baixar_arquivo(fat['links']['danfe'], os.path.join(pasta_final, nome), headers)

                # Baixa Boleto
                if 'boleto' in fat['links']:
                    nome = f"Boleto_{nome_empresa}_{num_nota}.pdf"
                    self._baixar_arquivo(fat['links']['boleto'], os.path.join(pasta_final, nome), headers)

        except Exception as e:
            self.logger.error(f"Erro MGE: {e}")
        finally:
            driver.quit()

    def _baixar_arquivo(self, url, path, headers):
        try:
            if os.path.exists(path): return
            r = self.session.get(url, headers=headers, stream=True)
            if r.status_code == 200:
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
                self.logger.info(f"Baixado: {os.path.basename(path)}")
        except Exception as e:
            self.logger.error(f"Falha download {url}: {e}")

if __name__ == "__main__":
    robot = MGERobot()
    robot.run()
