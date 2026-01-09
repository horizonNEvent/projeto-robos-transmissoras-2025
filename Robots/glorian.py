import os
import time
import glob
import logging
from datetime import datetime, date
from typing import Tuple

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

# Import BaseRobot
try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

class GlorianRobot(BaseRobot):
    """
    Robô para Portal Glorian.
    Usa Selenium.
    Fluxo: Login -> Notas Fiscais -> Pesquisa -> (Sem Filtro Contrato) -> Download Tudo
    """
    
    def __init__(self):
        super().__init__("glorian")
        self.driver = None
        self.wait = None
        self.url = "https://bp.glorian.com.br/bpglportal/"
        self.timeout_downloads = 700

    def _default_competencia(self) -> Tuple[int, int]:
        hoje = date.today()
        if hoje.month == 1:
            return hoje.year - 1, 12
        return hoje.year, hoje.month - 1

    def _wait_downloads(self, diretorio: str) -> bool:
        """Aguarda downloads terminarem observando .crdownload/.tmp e estabilidade de arquivos"""
        self.logger.info("Aguardando downloads...")
        inicio = time.time()
        ultima_atividade = time.time()
        
        def estado_arquivos():
            try:
                # Retorna lista de (nome, tam, mtime)
                return [(f.name, f.stat().st_size, f.stat().st_mtime) for f in os.scandir(diretorio)]
            except: return []

        estado_anterior = estado_arquivos()
        
        while True:
            temps = glob.glob(os.path.join(diretorio, "*.crdownload")) + \
                    glob.glob(os.path.join(diretorio, "*.tmp")) + \
                    glob.glob(os.path.join(diretorio, "*.part"))
            
            estado_atual = estado_arquivos()
            agora = time.time()

            # Se houve mudança ou tem arquivo temporário
            if temps or estado_atual != estado_anterior:
                ultima_atividade = agora
                estado_anterior = estado_atual
            
            # Se não tem temporários e passou X segundos sem mudança
            idle_time = 6.0
            if not temps and (agora - ultima_atividade) >= idle_time:
                return True
            
            if (agora - inicio) > self.timeout_downloads:
                self.logger.error("Timeout aguardando downloads.")
                return False
            
            time.sleep(1)

    def _fill(self, xpath: str, value: str):
        elem = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        try:
            elem.clear()
        except: pass
        
        # Tenta limpar robusto
        try:
            self.driver.execute_script("arguments[0].value = '';", elem)
        except:
            elem.send_keys(Keys.CONTROL + "a")
            elem.send_keys(Keys.DELETE)
            
        elem.send_keys(value)

    def _click(self, xpath: str):
        btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        try:
            btn.click()
        except:
            self.driver.execute_script("arguments[0].click();", btn)

    def run(self):
        # Args
        login = self.args.user
        senha = self.args.password
        
        if not login or not senha:
            self.logger.error("Login (--user) e Senha (--password) são obrigatórios.")
            return

        # Competencia
        ano, mes = self._default_competencia()
        if self.args.competencia: # YYYYMM
            try:
                c = self.args.competencia
                ano = int(c[:4])
                mes = int(c[4:6])
            except:
                self.logger.warning("Competência inválida, usando padrão.")

        output_dir = self.get_output_path()
        # Se quiser subpasta por data: output_dir = os.path.join(output_dir, f"{ano}{mes:02d}")
        os.makedirs(output_dir, exist_ok=True)

        # Configura Driver
        chrome_options = Options()
        prefs = {
            "download.default_directory": output_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.automatic_downloads": 1,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        # chrome_options.add_argument("--headless") # Habilitar futuramente se quiser
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20)
        self.driver.maximize_window()

        try:
            self.logger.info("Acessando portal Glorian...")
            self.driver.get(self.url)
            time.sleep(3)

            # Login
            self.logger.info("Realizando Login...")
            self._fill("//input[@placeholder='Login ou e-mail']", login)
            time.sleep(1)
            self._click("//td[contains(text(),'Próximo')]")
            time.sleep(2)
            self._fill("//input[@placeholder='Senha']", senha)
            time.sleep(1)
            self._click("//td[contains(text(),'Login')]")
            time.sleep(5)

            # Navegação
            self.logger.info("Acessando Notas Fiscais...")
            self._click("//p[contains(text(),'Notas Fiscais')]")
            time.sleep(10)
            
            # Pesquisa
            self.logger.info("Abrindo Pesquisa...")
            self._click("//div[@title='Pesquisa']")
            time.sleep(3)

            # --- FILTRO CONTRATO (COMENTADO A PEDIDO) ---
            # codigo_organizacao = "..."
            # self.logger.info(f"Filtrando contrato: {codigo_organizacao}")
            # self._fill("//input[@title='Organização de Contrato']", codigo_organizacao)
            # self.driver.switch_to.active_element.send_keys(Keys.TAB)
            # time.sleep(2)
            # --------------------------------------------

            self.logger.info(f"Filtrando Data: {mes}/{ano}")
            
            # Ano
            self._fill("//input[@title='Ano'][@maxlength='4'][@type='text']", str(ano))
            self.driver.switch_to.active_element.send_keys(Keys.TAB)
            time.sleep(2)

            # Mês (XPath Absoluto do User - deve ser estável no Glorian? Esperamos que sim)
            xpath_mes = "/html/body/div[1]/div/div/div/div[2]/div/div[2]/div/div[2]/div/div[3]/div/div[2]/div/div[3]/div/div/div/div[2]/div/div/div/div/div/div/div/div/div[2]/div/div/div/div/div/div/div[2]/div[3]/div/div/div/div[2]/div/table/tbody/tr[28]/td[2]/div/table/tbody/tr/td[2]/div/table/tbody/tr/td[1]/input"
            try:
                self._fill(xpath_mes, str(mes))
                self.driver.switch_to.active_element.send_keys(Keys.TAB)
            except:
                self.logger.warning("Falha ao preencher Mês com XPath absoluto. Tentando genérico...")
                # Fallback se o xpath absoluto falhar (ele é bem frágil)
                # Tentar achar inputs visiveis na area de pesquisa
                self._fill("//input[contains(@title, 'Mês') or contains(@id, 'mes')]", str(mes)) # Tentativa
            time.sleep(2)

            # Executar
            self.logger.info("Executando consulta...")
            self._click("//div[@title='Executar a consulta']")
            time.sleep(5)

            # Aumentar Paginação
            self.logger.info("Ajustando paginação para 500...")
            try:
                campo_qtd = self.wait.until(EC.presence_of_element_located((By.XPATH, "//input[@title='Quantidade de registro por página']")))
                # Tenta limpar/preencher
                try: campo_qtd.clear()
                except: pass
                campo_qtd.send_keys("500")
                campo_qtd.send_keys(Keys.ENTER)
                time.sleep(3)
            except Exception as e:
                self.logger.warning(f"Não conseguiu ajustar paginação: {e}")

            # Selecionar Todos
            self.logger.info("Selecionando todos os registros...")
            clicked_select = False
            for xp in [
                "//div[@title='SELECIONA TODOS os registros']", 
                "//div[contains(@title,'SELECIONA TODOS')]",
                "//div[@tabindex='0']//img[contains(@src, '57001330')]/parent::div"
            ]:
                try:
                    self._click(xp)
                    clicked_select = True
                    break
                except: continue
            
            if not clicked_select:
                # Tentativa JS
                 self.driver.execute_script("""
                    var els = document.querySelectorAll("div[title*='SELECIONA TODOS']");
                    if(els.length > 0) els[0].click();
                 """)
            time.sleep(2)

            # Downloads
            self.logger.info("Iniciando Downloads...")
            
            try:
                self.logger.info("- Boletos")
                self._click("//div[@title='Download do boleto']")
                time.sleep(1)
            except: self.logger.warning("Botão Boleto não achado/clicável")

            try:
                self.logger.info("- XMLs")
                self._click("//div[@title='Download do XML da NF-e.']")
                time.sleep(1)
            except: self.logger.warning("Botão XML não achado/clicável")

            try:
                self.logger.info("- DANFEs")
                self._click("//div[@title='Download do Danfe da NFe.']")
                time.sleep(1)
            except: self.logger.warning("Botão DANFE não achado/clicável")

            # Aguarda fim
            self._wait_downloads(output_dir)
            self.logger.info(f"Downloads finalizados em: {output_dir}")
            
            # Organização Pós-Download
            self._organizar_arquivos(output_dir)

        except Exception as e:
            self.logger.error(f"Erro fatal Glorian: {e}")
            # Em modo dev (headless=False) deixamos aberto pra debug se der erro? 
            # self.driver.quit()
        finally:
            if self.driver:
                self.driver.quit()

    def _organizar_arquivos(self, pasta_origem):
        """
        Organiza os arquivos baixados agrupando por Chave/Número da NF.
        Baseado no padrão:
          - NFe[CHAVE]... (XML e PDF)
          - boleto-NFe[CHAVE]... (PDF)
        """
        import shutil
        from pathlib import Path

        self.logger.info("Iniciando organização dos arquivos...")
        arquivos_por_nf = {}
        
        try:
            for arquivo in os.listdir(pasta_origem):
                path_completo = os.path.join(pasta_origem, arquivo)
                if os.path.isdir(path_completo): continue # Pula pastas
                
                nf_chave = None
                
                # Extração da chave
                # Ex: NFe1226014307611700024... -> 1226014307611700024...
                # Ex: boleto-NFe1226014307611700024...
                
                if arquivo.startswith('NFe'):
                    # Padrão: NFe[44 digitos]...
                    # Tenta extrair os primeiros 44 caracteres após NFe
                    try:
                        potential_key = arquivo[3:47] # NFe + 44 chars
                        if potential_key.isdigit() and len(potential_key) == 44:
                            nf_chave = potential_key
                    except: pass
                    
                elif arquivo.startswith('boleto-NFe'):
                    # Padrão: boleto-NFe[44 digitos]...
                    try:
                        potential_key = arquivo[10:54] # boleto-NFe + 44 chars
                        if potential_key.isdigit() and len(potential_key) == 44:
                            nf_chave = potential_key
                    except: pass
                
                if nf_chave:
                    if nf_chave not in arquivos_por_nf:
                        arquivos_por_nf[nf_chave] = []
                    arquivos_por_nf[nf_chave].append(arquivo)

            # Move arquivos
            for chave, lista_arquivos in arquivos_por_nf.items():
                if not lista_arquivos: continue
                
                # Nome da pasta: NF_{CHAVE}
                # Poderiamos tentar extrair o numero da NF da chave se necessario, 
                # mas usar a chave garante unicidade.
                nome_pasta = f"NF_{chave[:20]}" # Corta pra nao ficar gigante se for chave completa? Ou usa inteira?
                # Vamos usar prefixo + 8 digitos finais para ficar legivel? 
                # Melhor usar o que garante unicidade.
                nome_pasta = f"NF_{chave}"
                
                nova_pasta = os.path.join(pasta_origem, nome_pasta)
                os.makedirs(nova_pasta, exist_ok=True)
                
                for arq in lista_arquivos:
                    src = os.path.join(pasta_origem, arq)
                    dst = os.path.join(nova_pasta, arq)
                    try:
                        shutil.move(src, dst)
                        self.logger.info(f"Movido: {arq} -> {nome_pasta}")
                    except Exception as e:
                        self.logger.error(f"Erro ao mover {arq}: {e}")
            
            self.logger.info("Organização concluída.")

        except Exception as e:
            self.logger.error(f"Erro na organização: {e}")

if __name__ == "__main__":
    robot = GlorianRobot()
    robot.run()
