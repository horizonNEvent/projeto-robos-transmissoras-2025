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
import sqlite3
import re

# Import BaseRobot
try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class EquatorialRobotV2(BaseRobot):
    """
    Robô para Equatorial Transmissão V2.
    Adaptado para processar SP01, SP02, SP03, SP04, SP05, SP06, SP08.
    Busca a fatura mais recente.
    """

    def __init__(self):
        super().__init__("equatorial_v2")
        self.url = "https://www.equatorial-t.com.br/segunda-via-transmissao/"
        self.driver = None
        self.wait = None
        
        # Lista especifica solicitada: SP01, 02, 03, 04, 05, 06, 08
        self.target_spes = ["SP01", "SP02", "SP03", "SP04", "SP05", "SP06", "SP08"]

    def _parse_args(self):
        parser = argparse.ArgumentParser(description=f"Robô TUST: {self.robot_name}")
        parser.add_argument("--empresa", help="Nome da Empresa (ex: AETE, RE, AE, DE)")
        parser.add_argument("--user", help="CNPJ de login")
        parser.add_argument("--password", help="Senha (ignorado neste robô, mas mantido por compatibilidade)")
        parser.add_argument("--agente", help="Código ONS")
        parser.add_argument("--competencia", help="Mês referência (opcional, formato YYYYMM)")
        parser.add_argument("--output_dir", help="Pasta base para salvar os downloads", default="Downloads")
        parser.add_argument("--headless", action="store_true", help="Executar em modo headless")
        
        return parser.parse_args()

    def setup_driver(self):
        options = Options()
        options.add_argument("--start-maximized")
        if self.args.headless:
            options.add_argument("--headless") 
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
        """Fecha modais e avisos de cookies"""
        try:
            cookie_btn = WebDriverWait(self.driver, 2).until(
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            )
            self.driver.execute_script("arguments[0].click();", cookie_btn)
        except: pass

        try:
            modal_close = WebDriverWait(self.driver, 3).until(
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
            self.logger.info(f"      📥 [OK] Salvo: {filename}")
            return True
        except Exception as e:
            self.logger.error(f"      ❌ [ERRO] Falha no download {filename}: {e}")
            return False

    def process_spe(self, cnpj, codigo_ons, spe, base_output_dir):
        """Processa uma SPE específica buscando a fatura mais recente"""
        try:
            self.logger.info(f"  ⚡ [SPE] Iniciando verificação: {spe} ...")
            
            # 1. Acesso Inicial
            self.driver.get(self.url)
            self.close_popups()

            # 2. Login
            try:
                self.wait.until(EC.presence_of_element_located((By.ID, "user_spe")))
                
                inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
                if len(inputs) < 2:
                    self.logger.warning(f"    ⚠️ [{spe}] Campos de login não detectados.")
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
                self.close_popups()

                # Verifica se logou (se URL mudou ou se tem tabela)
                # O site Equatorial as vezes mantem a mesma URL base mas carrega conteudo via POST/ajax ou redirect 
                # Vamos assumir que se nao aparecer erro, logou.
                
                # 3. Navegação por Exercício
                # Vamos checar o ano atual e o ano anterior para garantir que pegamos a mais recente,
                # caso estejamos em Janeiro e a fatura seja de Dezembro.
                
                rows_to_check = []
                years_to_check = []
                
                current_year = datetime.now().year
                years_to_check.append(current_year)
                # Se estamos em Jan ou Fev, checamos ano anterior tambem
                if datetime.now().month <= 2:
                     years_to_check.append(current_year - 1)
                
                # Remove duplicados e ordena decrescente
                years_to_check = sorted(list(set(years_to_check)), reverse=True)

                if self.args.competencia:
                     try:
                        c = self.args.competencia.replace('/', '').replace('-', '')
                        comp_year = int(c[:4])
                        years_to_check = [comp_year]
                     except: pass

                for year in years_to_check:
                    target_url = f"{self.url}?exercicio={year}"
                    if str(year) not in self.driver.current_url:
                        self.logger.info(f"    📅 Verificando exercício {year}...")
                        self.driver.get(target_url)
                        time.sleep(2)
                        self.close_popups()

                    # Coleta linhas da tabela deste ano
                    page_rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                    if page_rows:
                        # Precisamos extrair os dados agora porque ao mudar de pagina os elementos perdem referencia
                        for row in page_rows:
                            try:
                                cols = row.find_elements(By.TAG_NAME, "td")
                                if len(cols) >= 7:
                                    # Extrai dados relevantes e links
                                    status = cols[0].text.strip().lower()
                                    if "aberto" not in status: # Filtra apenas em aberto
                                        continue
                                        
                                    mes = int(cols[3].text.strip())
                                    ano = int(cols[4].text.strip())
                                    
                                    xml_link = None
                                    pdf_link = None
                                    
                                    xml_as = cols[5].find_elements(By.TAG_NAME, "a")
                                    if xml_as: xml_link = xml_as[0].get_attribute("href")
                                        
                                    pdf_as = cols[6].find_elements(By.TAG_NAME, "a")
                                    if pdf_as: pdf_link = pdf_as[0].get_attribute("href")
                                    
                                    rows_to_check.append({
                                        'date': (ano, mes),
                                        'xml': xml_link,
                                        'pdf': pdf_link,
                                        'status': status
                                    })
                            except Exception as ex_row:
                                continue

                # 4. Encontrar a mais recente
                if not rows_to_check:
                    self.logger.info(f"    ⚪ [{spe}] Nada consta (Nenhuma fatura 'Em aberto').")
                    # Logout
                    self.driver.get("https://www.equatorial-t.com.br/login-cliente?action=logout")
                    time.sleep(1)
                    return

                # Ordena por data (Ano, Mes) decrescente
                rows_to_check.sort(key=lambda x: x['date'], reverse=True)
                most_recent = rows_to_check[0]
                
                ano_fatura, mes_fatura = most_recent['date']
                ano_fatura, mes_fatura = most_recent['date']
                self.logger.info(f"    ✅ [{spe}] Fatura Encontrada: {mes_fatura:02d}/{ano_fatura} (Status: {most_recent['status']})")

                # 5. Download
                # Creating structure: OUTPUT_DIR / AGENT_CODE / SPE / Files
                final_output_path = os.path.join(base_output_dir, str(codigo_ons), spe)
                os.makedirs(final_output_path, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if most_recent['xml']:
                    self.download_file(most_recent['xml'], final_output_path, f"NFe_EQUATORIAL_V2_{spe}_{timestamp}.xml")
                
                if most_recent['pdf']:
                    self.download_file(most_recent['pdf'], final_output_path, f"DANFE_EQUATORIAL_V2_{spe}_{timestamp}.pdf")

            except Exception as e:
                self.logger.error(f"    ❌ Erro no fluxo da SPE {spe}: {e}")

            # Logout
            self.driver.get("https://www.equatorial-t.com.br/login-cliente?action=logout")
            time.sleep(2)

        except Exception as e:
            self.logger.error(f"❌ Erro crítico na SPE {spe}: {e}")

    def run(self):
        self.logger.info(f"🚀 Iniciando Robô Equatorial V2 (Ciclo Completo)...")
        
        # Determine root and DB path
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(root_dir, "sql_app.db")
        
        agents_to_process = []
        target_agents_arg = self.args.agente
        target_list = [a.strip() for a in target_agents_arg.split(',') if a.strip()] if target_agents_arg else []

        # 1. Tenta carregar do Banco de Dados (Mais eficiente e descentralizado)
        try:
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                query = "SELECT codigo_ons, cnpj, nome_empresa FROM empresas"
                if target_list:
                    placeholders = ','.join(['?'] * len(target_list))
                    query += f" WHERE codigo_ons IN ({placeholders})"
                    cursor.execute(query, target_list)
                else:
                    cursor.execute(query)
                
                rows = cursor.fetchall()
                for row in rows:
                    if row[1]: # Se tem CNPJ
                        agents_to_process.append((row[0], row[1], row[2]))
                conn.close()
                if agents_to_process:
                    self.logger.info(f"📊 {len(agents_to_process)} agentes carregados via Banco de Dados.")
        except Exception as e:
            self.logger.warning(f"⚠️ Falha ao consultar banco de dados: {e}. Tentando fallback para JSON...")

        # 2. Fallback para JSON se DB falhou ou retornou vazio
        if not agents_to_process:
            json_path = os.path.join(root_dir, "Data", "empresas.equatorial.json")
            try:
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for group, agents in data.items():
                            for code, info in agents.items():
                                if target_list and str(code) not in target_list:
                                    continue
                                cnpj = info.get("cnpj") if isinstance(info, dict) else None
                                nome = info.get("nome") if isinstance(info, dict) else info
                                if cnpj:
                                    agents_to_process.append((code, cnpj, nome))
                    if agents_to_process:
                        self.logger.info(f"📄 {len(agents_to_process)} agentes carregados via JSON (Fallback).")
            except Exception as e:
                self.logger.error(f"❌ Erro no fallback JSON: {e}")

        if not agents_to_process:
            self.logger.error("❌ Nenhum agente com CNPJ encontrado para processamento.")
            return

        base_output_dir = self.get_output_path()
        self.setup_driver()
        
        try:
            for agent_code, cnpj, nome_agente in agents_to_process:
                self.logger.info(f"🏢 AGENTE: {nome_agente} ({agent_code}) | CNPJ: {cnpj}")
                for spe in self.target_spes:
                    self.process_spe(cnpj, agent_code, spe, base_output_dir)
        finally:
            if self.driver:
                self.driver.quit()
        
        self.logger.info("🏁 Execução Concluída.")

if __name__ == "__main__":
    robot = EquatorialRobotV2()
    robot.run()
