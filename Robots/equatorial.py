import argparse
import logging
import os
import time
import json
import requests
import urllib3
from pathlib import Path
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

# Import BaseRobot
# O sistema executa o script como modulo principal ou via import,
# entao precisamos garantir acesso a classe BaseRobot no mesmo diretorio.
try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class EquatorialRobot(BaseRobot):
    """
    Robô para Equatorial Transmissão.
    Suporta execução individual (--spe SP01) ou em lote (todas SPEs).
    """

    def __init__(self):
        super().__init__("equatorial")
        self.url = "https://www.equatorial-t.com.br/segunda-via-transmissao/"
        self.driver = None
        self.wait = None
        
        # Lista padrao de SPEs para varredura completa
        self.knowledge_base_spes = ["SP01", "SP02", "SP03", "SP04", "SP05", "SP06", "SP08"]

    def _parse_args(self):
        # Estende o parser padrao para incluir --spe
        parser = argparse.ArgumentParser(description=f"Robô TUST: {self.robot_name}")
        parser.add_argument("--empresa", help="Nome da Empresa (ex: AETE, RE, AE, DE)")
        parser.add_argument("--user", help="CNPJ de login")
        parser.add_argument("--password", help="Senha (nao usado na Equatorial, mas padrao)")
        parser.add_argument("--agente", help="Código ONS")
        parser.add_argument("--competencia", help="Mês referência (opcional)")
        parser.add_argument("--output_dir", help="Pasta base para salvar os downloads")
        
        # Novo argumento especifico
        parser.add_argument("--spe", help="Código da SPE específica (ex: SP01). Se vazio, roda todas.")
        parser.add_argument("--headless", action="store_true", help="Executar em modo headless")
        
        return parser.parse_args()

    def setup_driver(self):
        options = Options()
        options.add_argument("--start-maximized")
        # Se estiver rodando no servidor, idealmente seria headless=True,
        # mas mantemos False para debug visual se o usuario preferir (ou parametrizavel)
        # options.add_argument("--headless") 
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        prefs = {
            "plugins.always_open_pdf_externally": True,
            "download.prompt_for_download": False,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 15)

    def close_popups(self):
        """Fecha modais e avisos de cookies (Verificação Robusta)"""
        # 1. Cookies
        try:
            cookie_btn = WebDriverWait(self.driver, 2).until(
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            )
            self.driver.execute_script("arguments[0].click();", cookie_btn)
        except: pass

        # 2. Modal Chato (gmz-modal-close)
        try:
            modal_close = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((By.ID, "gmz-modal-close"))
            )
            # Tenta clicar via JS para garantir
            self.driver.execute_script("arguments[0].click();", modal_close)
            self.logger.info("Modal 'gmz-modal-close' fechado.")
        except: pass

    def download_file(self, url, dest_folder, filename):
        """Executa download usando a sessão do navegador"""
        try:
            session = requests.Session()
            # Copia cookies do Selenium para o Requests
            for cookie in self.driver.get_cookies():
                session.cookies.set(cookie['name'], cookie['value'])
            
            headers = {"User-Agent": self.driver.execute_script("return navigator.userAgent;")}
            response = session.get(url, headers=headers, stream=True, verify=False)
            response.raise_for_status()
            
            filepath = os.path.join(dest_folder, filename)
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            self.logger.info(f"Salvo: {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Erro no download {filename}: {e}")
            return False

    def process_spe(self, cnpj, codigo_ons, spe, base_output_dir, date_filter=None):
        """Processa uma SPE específica"""
        try:
            self.logger.info(f"Processando SPE: {spe} | ONS: {codigo_ons}")
            
            # 1. Acesso Inicial
            self.driver.get(self.url)
            self.close_popups() # Tenta fechar modal logo de entrada

            # Preenchimento do Login
            try:
                # Aguarda inputs
                self.wait.until(EC.presence_of_element_located((By.ID, "user_spe")))
                
                inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
                if len(inputs) < 2:
                    self.logger.warning(f"[{spe}] Inputs de login não encontrados.")
                    return

                # Limpa e preenche
                inputs[0].clear()
                inputs[0].send_keys(cnpj)
                inputs[1].clear()
                inputs[1].send_keys(codigo_ons)
                
                spe_input = self.driver.find_element(By.ID, "user_spe")
                spe_input.clear()
                spe_input.send_keys(spe)
                spe_input.send_keys(Keys.ENTER)
                
                # Aguarda processamento do Login
                time.sleep(3)
                
                # 2. Pós-Login: Fecha modal novamente se aparecer
                self.close_popups()

                # Determine target year for URL (default to previous month if no filter)
                if date_filter:
                    target_year = date_filter[0]
                else:
                    # Use previous month's year (e.g. In Jan 2026 -> Dec 2025)
                    prev_month_date = datetime.now().replace(day=1) - timedelta(days=1)
                    target_year = prev_month_date.year
                
                # 3. Navegação por Exercicio (Ano)
                # O usuario indicou usar o link ou input. Link com parametro é mais direto.
                target_url = f"{self.url}?exercicio={target_year}"
                
                if str(target_year) not in self.driver.current_url:
                     self.logger.info(f"Redirecionando para exercício {target_year}: {target_url}")
                     self.driver.get(target_url)
                     time.sleep(2) # Espera carregar
                     
                     # 4. Pós-Redirecionamento: Fecha modal novamente (crítico)
                     self.close_popups()

                # Busca faturas na tabela
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                
                target_date = None
                target_row = None
                
                # ... (rest of logic)
                
                # Se nao tiver filtro de data, busca a mais recente
                # Se tiver, busca a data especifica (YYYYMM)
                
                latest_date_tuple = None

                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) < 7: continue
                    
                    status = cols[0].text.strip().lower()
                    
                    # Logica original pedia 'em aberto'. Vamos manter, mas flexibilizar? 
                    # Por enquanto mantem 'aberto' para nao baixar coisas velhas pagas.
                    if "aberto" not in status:
                        continue
                    
                    try:
                        mes_txt = cols[3].text.strip()
                        ano_txt = cols[4].text.strip()
                        
                        mes = int(mes_txt)
                        ano = int(ano_txt)
                        
                        # Se temos um filtro de competencia especifico
                        if date_filter: # tuple (YYYY, MM)
                            if (ano, mes) == date_filter:
                                target_row = row
                                target_date = (ano, mes)
                                break # Achamos a exata
                        else:
                            # Logica de "Mais Recente"
                            current_val = (ano, mes)
                            if latest_date_tuple is None or current_val > latest_date_tuple:
                                latest_date_tuple = current_val
                                target_row = row
                                target_date = latest_date_tuple
                    except:
                        continue

                # Se nao achou nada
                if not target_row:
                    msg = f"Nenhuma fatura 'Em aberto' encontrada Para {spe}."
                    if date_filter: msg += f" Comp: {date_filter}"
                    self.logger.info(msg)
                    self.driver.get("https://www.equatorial-t.com.br/login-cliente?action=logout")
                    time.sleep(1)
                    return

                # Processa a linha encontrada
                cols = target_row.find_elements(By.TAG_NAME, "td")
                ano_fatura, mes_fatura = target_date
                
                # Caminho: Downloads/EQUATORIAL/SP01/
                # Ajuste a gosto do usuario. Ele citou: "ter umas com todas... e outros robos individuais"
                # Vamos padronizar: sempre dentro da pasta da SPE.
                
                final_output_path = os.path.join(base_output_dir, spe)
                os.makedirs(final_output_path, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Links
                xml_links = cols[5].find_elements(By.TAG_NAME, "a")
                pdf_links = cols[6].find_elements(By.TAG_NAME, "a")

                if xml_links:
                    self.download_file(xml_links[0].get_attribute("href"), final_output_path, f"NFe_EQUATORIAL_{spe}_{timestamp}.xml")
                
                if pdf_links:
                    self.download_file(pdf_links[0].get_attribute("href"), final_output_path, f"DANFE_EQUATORIAL_{spe}_{timestamp}.pdf")

            except Exception as e:
                self.logger.error(f"Erro no fluxo da SPE {spe}: {e}")

            # Logout
            self.driver.get("https://www.equatorial-t.com.br/login-cliente?action=logout")
            time.sleep(2)

        except Exception as e:
            self.logger.error(f"Erro geral na SPE {spe}: {e}")

    def run(self):
        self.logger.info(f"Iniciando Robô Equatorial...")
        
        # Validacao de argumentos minimos
        if not self.args.user or not self.args.agente:
            self.logger.error("CNPJ (--user) e Agente ONS (--agente) sao obrigatorios.")
            return

        cnpj = self.args.user
        ons = self.args.agente
        base_output_dir = self.get_output_path()
        
        # Parse Competencia se houver
        date_filter = None
        if self.args.competencia:
            try:
                c = self.args.competencia.replace('/', '').replace('-', '')
                date_filter = (int(c[:4]), int(c[4:6])) # (2026, 1)
            except:
                self.logger.warning("Competência inválida ignorada (use YYYYMM). Usando busca automatica (mais recente).")

        # Inicia Driver
        self.setup_driver()
        
        try:
            # Decide se roda UMA ou TODAS baseado na SENHA (workaround para nao alterar front)
            # Se password for passado e nao for 'ALL', usa como filtro de SPE.
            spes_to_run = []
            senha_arg = self.args.password
            
            # Prioridade: argumento --spe explicito > password > tudo
            if self.args.spe:
                spes_to_run = [self.args.spe]
                self.logger.info(f"Modo Individual (Arg): SPE {self.args.spe}")
            elif senha_arg and senha_arg.strip().upper() not in ['ALL', 'TODAS', '', 'NONE', 'NULL']:
                target = senha_arg.strip().upper()
                spes_to_run = [target]
                self.logger.info(f"Modo Individual (Senha): SPE {target}")
            else:
                # Modo Batch (Todas Conhecidas)
                spes_to_run = self.knowledge_base_spes
                self.logger.info(f"Modo Batch: Executando {len(spes_to_run)} SPEs...")

            for spe in spes_to_run:
                self.process_spe(cnpj, ons, spe, base_output_dir, date_filter)
        
        finally:
            if self.driver:
                self.driver.quit()
        
        self.logger.info("Execução Concluída.")

if __name__ == "__main__":
    robot = EquatorialRobot()
    robot.run()
