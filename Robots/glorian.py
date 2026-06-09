import os
import time
import glob
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
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
    Fluxo: Login -> 'Mês corrente' -> Paginação 500 -> Seleciona Todos -> Download Tudo
    """
    
    def __init__(self):
        super().__init__("glorian")
        self.driver = None
        self.wait = None
        self.url = "https://bp.glorian.com.br/bpglportal/"
        self.timeout_downloads = 700

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

    def _click_retry(self, xpath: str, tentativas: int = 4, espera: float = 2.0) -> bool:
        """Tenta clicar várias vezes (útil para botões instáveis como o de Login)."""
        for i in range(1, tentativas + 1):
            try:
                btn = self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                # Garante visibilidade na viewport
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", btn
                    )
                except:
                    pass
                try:
                    btn.click()
                except:
                    self.driver.execute_script("arguments[0].click();", btn)
                self.logger.info(f"Clique OK (tentativa {i}): {xpath}")
                return True
            except Exception as e:
                self.logger.warning(
                    f"Falha ao clicar (tentativa {i}/{tentativas}) em {xpath}: {e}"
                )
                time.sleep(espera)
        self.logger.error(f"Não foi possível clicar após {tentativas} tentativas: {xpath}")
        return False

    def _senha_visivel(self, timeout: float = 4.0) -> bool:
        """Verifica se o campo de senha apareceu (indica que 'Próximo' funcionou)."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@placeholder='Senha']"))
            )
            return True
        except:
            return False

    def _clicar_proximo(self) -> bool:
        """
        Clica no botão 'Próximo' (linha de tabela com <div tabindex=0> interno).
        Tenta XPaths -> eventos de mouse realistas via JS. Valida pelo campo Senha.
        """
        xpaths = [
            "//td[contains(normalize-space(.),'Próximo')]",
            "//tr//td[contains(text(),'Próximo')]",
            "//div[@tabindex='0' and contains(normalize-space(.),'Próximo')]",
            "//*[normalize-space(text())='Próximo']",
        ]

        for xp in xpaths:
            try:
                btn = self.wait.until(EC.presence_of_element_located((By.XPATH, xp)))
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", btn
                    )
                except:
                    pass
                time.sleep(0.5)
                try:
                    btn.click()
                except:
                    self.driver.execute_script("arguments[0].click();", btn)
                self.logger.info(f"'Próximo' clicado via XPath: {xp}")
                if self._senha_visivel():
                    return True
            except Exception as e:
                self.logger.debug(f"XPath 'Próximo' falhou ({xp}): {e}")
                continue

        # Fallback JS: acha o elemento visível com texto exato 'Próximo' e dispara
        # uma sequência realista de eventos de mouse.
        self.logger.warning("XPaths de 'Próximo' falharam. Tentando via JavaScript...")
        try:
            achou = self.driver.execute_script(
                """
                var alvo = null;
                var els = document.querySelectorAll('td, div, span, a, button, tr');
                for (var i = 0; i < els.length; i++) {
                    var el = els[i];
                    if (el.textContent && el.textContent.trim() === 'Próximo' && el.offsetHeight > 0) {
                        alvo = el; break;
                    }
                }
                if (!alvo) return false;
                // Sobe até um elemento com onclick/tabindex (handler real), se houver
                var clickAlvo = alvo.querySelector("div[tabindex='0']") || alvo;
                var opts = { bubbles: true, cancelable: true, view: window };
                ['mouseenter','mouseover','mousedown','mouseup'].forEach(function(t){
                    clickAlvo.dispatchEvent(new MouseEvent(t, opts));
                });
                clickAlvo.click();
                return true;
                """
            )
            if achou:
                self.logger.info("'Próximo' clicado via JavaScript (eventos de mouse)")
                if self._senha_visivel(timeout=5.0):
                    return True
                self.logger.warning("Clique JS executado, mas campo de senha não apareceu.")
            else:
                self.logger.error("JavaScript não encontrou o botão 'Próximo'.")
        except Exception as e:
            self.logger.error(f"Erro no JS de 'Próximo': {e}")

        return False

    def _clicar_proximo_retry(self, tentativas: int = 3) -> bool:
        """Tenta clicar em 'Próximo' várias vezes com delay progressivo (2s, 4s, 6s)."""
        for i in range(1, tentativas + 1):
            self.logger.info(f"Tentativa {i}/{tentativas} para clicar em 'Próximo'...")
            if self._clicar_proximo():
                self.logger.info("'Próximo' OK: campo de senha disponível.")
                return True
            if i < tentativas:
                time.sleep(2 * i)
        self.logger.error("Falha ao avançar com 'Próximo' após todas as tentativas.")
        return False

    def _login_concluido(self, timeout: float = 10.0) -> bool:
        """Verifica se o login foi aceito (saiu da tela de credenciais)."""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: (
                    "/app" in d.current_url
                    or len(d.find_elements(By.XPATH, "//input[@placeholder='Senha']")) == 0
                    or len(d.find_elements(By.XPATH, "//p[@class='branch']")) > 0
                )
            )
            return True
        except:
            return False

    def _enviar_login_enter(self) -> bool:
        """Submete o login com ENTER no campo de senha (menos detectável que clique)."""
        try:
            senha_input = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Senha']"))
            )
            senha_input.click()
            time.sleep(0.3)
            senha_input.send_keys(Keys.ENTER)
            self.logger.info("Login enviado via ENTER no campo de senha")
            return self._login_concluido()
        except Exception as e:
            self.logger.warning(f"ENTER no campo de senha falhou: {e}")
            return False

    def _clicar_login(self) -> bool:
        """
        Tenta submeter o login: XPath -> ActionChains -> JS -> ENTER.
        Valida pelo menu pós-login ou sumiço do campo de senha.
        """
        xpaths = [
            "//td[contains(normalize-space(.),'Login')]",
            "//tr[contains(.//td,'Login')]",
            "//div[@tabindex='0' and contains(normalize-space(.),'Login')]",
            "//*[normalize-space(text())='Login']",
        ]

        for xp in xpaths:
            try:
                btn = self.wait.until(EC.presence_of_element_located((By.XPATH, xp)))
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", btn
                )
                time.sleep(0.5)
                try:
                    btn.click()
                except:
                    self.driver.execute_script("arguments[0].click();", btn)
                self.logger.info(f"'Login' clicado via XPath: {xp}")
                if self._login_concluido(timeout=6.0):
                    return True
            except Exception as e:
                self.logger.debug(f"XPath 'Login' falhou ({xp}): {e}")
                continue

        # ActionChains: movimento real de mouse até o botão
        for xp in xpaths[:2]:
            try:
                btn = self.wait.until(EC.presence_of_element_located((By.XPATH, xp)))
                ActionChains(self.driver).move_to_element(btn).pause(0.5).click().perform()
                self.logger.info(f"'Login' clicado via ActionChains: {xp}")
                if self._login_concluido(timeout=6.0):
                    return True
            except Exception as e:
                self.logger.debug(f"ActionChains 'Login' falhou ({xp}): {e}")

        # Fallback JS com eventos de mouse
        self.logger.warning("Cliques Selenium falharam. Tentando 'Login' via JavaScript...")
        try:
            achou = self.driver.execute_script(
                """
                var alvo = null;
                var els = document.querySelectorAll('td, div, span, a, button, tr');
                for (var i = 0; i < els.length; i++) {
                    var el = els[i];
                    if (el.textContent && el.textContent.trim() === 'Login' && el.offsetHeight > 0) {
                        alvo = el; break;
                    }
                }
                if (!alvo) return false;
                var clickAlvo = alvo.querySelector("div[tabindex='0']") || alvo;
                var opts = { bubbles: true, cancelable: true, view: window };
                ['mouseenter','mouseover','mousedown','mouseup'].forEach(function(t){
                    clickAlvo.dispatchEvent(new MouseEvent(t, opts));
                });
                clickAlvo.click();
                return true;
                """
            )
            if achou and self._login_concluido(timeout=6.0):
                self.logger.info("'Login' aceito após clique JavaScript")
                return True
        except Exception as e:
            self.logger.warning(f"JS de 'Login' falhou: {e}")

        # ENTER costuma contornar bloqueio de clique automatizado
        return self._enviar_login_enter()

    def _clicar_login_retry(self, tentativas: int = 3) -> bool:
        """Tenta submeter login com delay progressivo entre tentativas."""
        for i in range(1, tentativas + 1):
            self.logger.info(f"Tentativa {i}/{tentativas} para submeter login...")
            if self._clicar_login():
                self.logger.info("Login OK: portal autenticado.")
                return True
            if i < tentativas:
                time.sleep(2 * i)
        self.logger.error("Falha ao autenticar após todas as tentativas.")
        return False

    def _criar_driver(self, output_dir: str):
        """Cria Chrome com prefs de download e flags anti-detecção básicas."""
        chrome_options = Options()
        prefs = {
            "download.default_directory": output_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.automatic_downloads": 1,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        # chrome_options.add_argument("--headless")

        driver = webdriver.Chrome(options=chrome_options)
        try:
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": (
                        "Object.defineProperty(navigator, 'webdriver', "
                        "{ get: () => undefined });"
                    )
                },
            )
        except Exception as e:
            self.logger.warning(f"Não foi possível aplicar script anti-detecção: {e}")
        return driver

    def _clicar_mes_corrente(self):
        """Clica no item de menu 'Mês corrente' (p.branch, 1º item do menu)."""
        seletores = [
            "//p[@class='branch' and contains(normalize-space(.), 'Mês corrente')]",
            "//p[contains(text(),'Mês corrente')]",
            "//ul[contains(@class,'C_37')]//li[1]//p[@class='branch']",
            "//ul[contains(@class,'C_37')]//li[1]//p",
            "//p[@class='branch']",
        ]
        for xp in seletores:
            try:
                self._click(xp)
                self.logger.info(f"'Mês corrente' clicado via: {xp}")
                return
            except:
                continue

        # Fallback JS: procura pelo texto entre os <p class="branch">
        self.logger.warning("XPaths falharam para 'Mês corrente'. Tentando via JS...")
        self.driver.execute_script(
            """
            var ps = document.querySelectorAll('p.branch');
            for (var i = 0; i < ps.length; i++) {
                if (ps[i].textContent.indexOf('Mês corrente') >= 0) { ps[i].click(); return; }
            }
            if (ps.length > 0) { ps[0].click(); }
            """
        )

    def run(self):
        # Args
        login = self.args.user
        senha = self.args.password
        
        if not login or not senha:
            self.logger.error("Login (--user) e Senha (--password) são obrigatórios.")
            return

        output_dir = self.get_output_path()
        # Se quiser subpasta por data: output_dir = os.path.join(output_dir, f"{ano}{mes:02d}")
        os.makedirs(output_dir, exist_ok=True)

        self.driver = self._criar_driver(output_dir)
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
            if not self._clicar_proximo_retry(tentativas=3):
                # Último recurso: ENTER no campo de login
                self.logger.warning("Tentando avançar com ENTER no campo de login...")
                self.driver.switch_to.active_element.send_keys(Keys.ENTER)
                if not self._senha_visivel(timeout=5.0):
                    self.logger.error("Não foi possível avançar para a senha. Abortando.")
                    return
            time.sleep(1)

            self._fill("//input[@placeholder='Senha']", senha)
            time.sleep(2)
            if not self._clicar_login_retry(tentativas=3):
                self.logger.error("Não foi possível autenticar no portal. Abortando.")
                return
            time.sleep(3)

            # Navegação (site simplificado): clica em 'Mês corrente'
            # Já traz os registros do mês corrente (notas mais atualizadas),
            # sem precisar definir mês e ano manualmente.
            self.logger.info("Acessando 'Mês corrente'...")
            self._clicar_mes_corrente()
            time.sleep(10)

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
                self.logger.info("- XMLs")
                self._click("//div[@title='Download do XML da NF-e.']")
                time.sleep(1)
            except: self.logger.warning("Botão XML não achado/clicável")

            
            try:
                self.logger.info("- Boletos")
                self._click("//div[@title='Download do boleto']")
                time.sleep(1)
            except: self.logger.warning("Botão Boleto não achado/clicável")
            time.sleep(3)
            # try:
            #     self.logger.info("- XMLs")
            #     self._click("//div[@title='Download do XML da NF-e.']")
            #     time.sleep(1)
            # except: self.logger.warning("Botão XML não achado/clicável")

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
