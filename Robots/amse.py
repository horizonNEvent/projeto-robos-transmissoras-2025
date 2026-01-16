import requests
from bs4 import BeautifulSoup
import logging
import argparse
import os
from urllib.parse import urlparse, parse_qs, urlencode
import time
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys

# Ajustando path para encontrar módulos locais se rodar da pasta Robots/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar modelos do Backend
try:
    from app.backend.models import Transmissora, Base
except ImportError:
    # Fallback se a estrutura de pastas não estiver perfeita no sys.path
    from models import Transmissora, Base # type: ignore

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AMSE")

# Configuração DB
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sql_app.db')
DATABASE_URL = f"sqlite:///{DB_PATH}"

class AmseScraper:
    def __init__(self, output_dir=None):
        self.session = requests.Session()
        self.base_url = "https://amse.ons.org.br/intunica/menu.aspx"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive"
        }
        self.session.headers.update(self.headers)
        
        from utils_paths import get_base_download_path, ensure_dir
        self.target_dir = output_dir or get_base_download_path("AMSE")
        ensure_dir(self.target_dir)

    def get_hidden_fields(self, html_content):
        """Extracts standard ASP.NET hidden fields from HTML."""
        soup = BeautifulSoup(html_content, 'html.parser')
        data = {}
        
        fields = ['__VIEWSTATE', '__VIEWSTATEGENERATOR', '__EVENTVALIDATION', '__EVENTTARGET', '__EVENTARGUMENT']
        
        for field in fields:
            element = soup.find('input', {'id': field})
            if element:
                value = element.get('value', '')
                if value is None: value = '' # Handle None
                data[field] = value
        
        return data

    def login(self, username, password):
        """Attempts to log in to the AMSE portal."""
        logger.info(f"Initializing login process for user {username}...")
        
        try:
            logger.info(f"Fetching GET request to {self.base_url}...")
            response = self.session.get(self.base_url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to load login page: {e}")
            return False

        payload = self.get_hidden_fields(response.text)
        
        payload.update({
            'txtLogin': username,
            'txtSenha': password,
            'btnOk.x': '9', 
            'btnOk.y': '6'  
        })
        
        try:
            logger.info("Sending POST request with credentials...")
            post_response = self.session.post(self.base_url, data=payload)
            post_response.raise_for_status()
            
            soup = BeautifulSoup(post_response.text, 'html.parser')
            
            if soup.find('input', {'id': 'txtLogin'}):
                logger.warning("Login failed. Login form still present.")
                return False

            logger.info(f"Login successful. Landing URL: {post_response.url}")
            
            # --- Decide Perfil Logic ---
            url_decide_perfil = "https://amse.ons.org.br/intunica/DecidePerfil.aspx"
            response_decide = self.session.get(url_decide_perfil)
            
            if "com mais do que um perfil definido" in response_decide.text:
                logger.info("Multiple profiles detected. Selecting AMSE_AGEUS...")
                
                hidden_fields = self.get_hidden_fields(response_decide.text)
                
                # POST 1
                payload_1 = hidden_fields.copy()
                payload_1.update({
                    '__EVENTTARGET': 'drpDownSistema',
                    '__EVENTARGUMENT': '',
                    '__LASTFOCUS': '',
                    'drpDownSistema': 'AMSE      ',
                    'ddwListaPerfis': ' ',
                    'rdBtnEscolha': 'AGE'
                })
                resp_1 = self.session.post(url_decide_perfil, data=payload_1)
                hidden_fields_1 = self.get_hidden_fields(resp_1.text)
                
                # POST 2
                payload_2 = hidden_fields_1.copy()
                payload_2.update({
                    '__EVENTTARGET': 'ddwListaPerfis',
                    '__EVENTARGUMENT': '',
                    '__LASTFOCUS': '',
                    'drpDownSistema': 'AMSE      ',
                    'ddwListaPerfis': 'AMSE_AGEUS - AMSE - Agentes de Distribuição, Geração, CL, Importação e Exportação                                ',
                    'rdBtnEscolha': 'AGE'
                })
                resp_2 = self.session.post(url_decide_perfil, data=payload_2)
                hidden_fields_2 = self.get_hidden_fields(resp_2.text)

                # POST 3 (Confirm)
                payload_3 = hidden_fields_2.copy()
                payload_3.update({
                    '__EVENTTARGET': '',
                    '__EVENTARGUMENT': '',
                    '__LASTFOCUS': '',
                    'drpDownSistema': 'AMSE      ',
                    'ddwListaPerfis': 'AMSE_AGEUS - AMSE - Agentes de Distribuição, Geração, CL, Importação e Exportação                                ',
                    'rdBtnEscolha': 'AGE',
                    'drpDownAgeCos': ' ',
                    'ImageBtnConfirmar.x': '19',
                    'ImageBtnConfirmar.y': '13'
                })
                self.session.post(url_decide_perfil, data=payload_3)
                logger.info("Profile selection completed.")

            # --- Menu Principal ---
            url_menu = "https://amse.ons.org.br/intunica/menuprincipal.aspx"
            response_menu = self.session.get(url_menu)
            
            soup_menu = BeautifulSoup(response_menu.text, 'html.parser')
            frame_foco = soup_menu.find('frame', {'name': 'foco'})
            foco_input = soup_menu.find('input', {'name': 'foco'})
            
            full_next_url = None
            if frame_foco:
                foco_value = frame_foco.get('src', '')
                next_url = foco_value.replace("&amp;", "&")
                full_next_url = f"https://amse.ons.org.br{next_url}"
            elif foco_input:
                foco_value = foco_input.get('value', '')
                next_url = foco_value.replace("&amp;", "&")
                full_next_url = f"https://amse.ons.org.br{next_url}"
            
            if full_next_url:
                resp_integracao = self.session.get(full_next_url)
                current_url = resp_integracao.url
                
                # --- Navigate to Report ---
                base_report_url = "https://amse.ons.org.br/amse/amse/webforms/relatorios/AMSE_frm_RelCadastroGeral.aspx"
                parsed_url = urlparse(current_url)
                query_params = parse_qs(parsed_url.query)
                query_params['compatibilityMode'] = 'IE=8,chrome=1'
                report_url = f"{base_report_url}?{urlencode(query_params, doseq=True)}"
                
                return self.process_report(report_url)
            else:
                logger.error("Could not find integration URL in menu.")
                return False

        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    def process_report(self, report_url):
        logger.info(f"Accessing report URL...")
        resp_report = self.session.get(report_url)
        
        max_retries = 60
        retry_interval = 5
        
        for attempt in range(max_retries):
            soup_rep = BeautifulSoup(resp_report.text, 'html.parser')
            status_span = soup_rep.find('span', {'id': 'status_relatorio'})
            status_text = status_span.get_text(strip=True) if status_span else ""
            
            logger.info(f"Status ({attempt+1}/{max_retries}): {status_text}")
            
            # Case 1: Processing
            if "PROCESSAMENTO" in status_text.upper():
                # Check dropdown
                ddl = soup_rep.find('select', {'id': 'ddl_exibir'})
                selected_option = ddl.find('option', {'selected': 'selected'}) if ddl else None
                current_val = selected_option['value'] if selected_option else '0'
                
                if current_val != '2':
                    logger.info("Switching to report Type 2 (Processing)...")
                    hidden_fields_opt = self.get_hidden_fields(resp_report.text)
                    payload_opt = hidden_fields_opt.copy()
                    payload_opt.update({'__EVENTTARGET': 'ddl_exibir', 'ddl_exibir': '2'})
                    resp_report = self.session.post(report_url, data=payload_opt)
                    continue
                
                time.sleep(retry_interval)
                resp_report = self.session.get(report_url)
                continue
                
            # Case 2: Available
            is_status_available = "DISPONIBILIZADO" in status_text.upper()
            btn_baixar = soup_rep.find('input', {'id': 'ibt_Baixar'})
            is_btn_enabled = btn_baixar and not btn_baixar.has_attr('disabled')
            
            if is_status_available or is_btn_enabled:
                logger.info("Report available. Preparing to download...")
                
                # Check dropdown again
                ddl = soup_rep.find('select', {'id': 'ddl_exibir'})
                selected_option = ddl.find('option', {'selected': 'selected'}) if ddl else None
                current_val = selected_option['value'] if selected_option else '0'
                
                if current_val != '2':
                    logger.info("Switching to Type 2 before download...")
                    hidden_fields_opt = self.get_hidden_fields(resp_report.text)
                    payload_opt = hidden_fields_opt.copy()
                    payload_opt.update({'__EVENTTARGET': 'ddl_exibir', 'ddl_exibir': '2'})
                    resp_report = self.session.post(report_url, data=payload_opt)
                    continue
                
                # Download
                hidden_fields_dl = self.get_hidden_fields(resp_report.text)
                payload_dl = hidden_fields_dl.copy()
                payload_dl.update({
                    '__EVENTTARGET': '', '__EVENTARGUMENT': '',
                    'ddl_exibir': '2', 'ibt_Baixar.x': '30', 'ibt_Baixar.y': '5'
                })
                
                resp_download = self.session.post(report_url, data=payload_dl, stream=True)
                
                if resp_download.status_code == 200:
                    filename = os.path.join(self.target_dir, "RelatorioCadastroGeral.xls")
                    with open(filename, 'wb') as f:
                        for chunk in resp_download.iter_content(chunk_size=8192):
                            f.write(chunk)
                    logger.info(f"Downloaded: {filename}")
                    return filename
                else:
                    logger.error(f"Download failed: {resp_download.status_code}")
                    return False

            # Case 3: Request Generation
            ddl = soup_rep.find('select', {'id': 'ddl_exibir'})
            if ddl:
                selected_option = ddl.find('option', {'selected': 'selected'})
                current_val = selected_option['value'] if selected_option else '0'
            else:
                 current_val = '0'

            if current_val != '2':
                hidden_fields_opt = self.get_hidden_fields(resp_report.text)
                payload_opt = hidden_fields_opt.copy()
                payload_opt.update({'__EVENTTARGET': 'ddl_exibir', 'ddl_exibir': '2'})
                resp_report = self.session.post(report_url, data=payload_opt)
                continue

            logger.info("Clicking Excel Generation...")
            hidden_fields_gen = self.get_hidden_fields(resp_report.text)
            payload_gen = hidden_fields_gen.copy()
            payload_gen.update({
                '__EVENTTARGET': '', '__EVENTARGUMENT': '',
                'ddl_exibir': '2', 'ibt_Excel.x': '35', 'ibt_Excel.y': '10'
            })
            resp_report = self.session.post(report_url, data=payload_gen)
        
        return False

class AmseUpdater:
    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def process_file(self, file_path):
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return

        logger.info(f"Reading file: {file_path}")
        try:
            # Using read_excel with openpyxl/xlrd automatically determined
            df = pd.read_excel(file_path)
        except Exception as e:
            logger.error(f"Error reading Excel: {e}")
            return

        # Normalize columns: Uppercase, strip, and remove encoding mojibake if simple
        df.columns = [str(c).upper().strip() for c in df.columns]
        logger.info(f"Columns found: {df.columns.tolist()}")
        
        # Mapeamento baseado no RelatorioCadastroGeral.xls inspecionado
        # Colunas esperadas: 'CDIGO', 'SIGLA DO AGENTE', 'RAZO SOCIAL', 'CNPJ'
        
        session = self.Session()
        updated_count = 0
        new_count = 0
        
        try:
            for index, row in df.iterrows():
                # Encontrar colunas chave independente de encoding ()
                col_cnpj = next((c for c in df.columns if 'CNPJ' in c), None)
                col_nome = next((c for c in df.columns if 'RAZ' in c and 'SOCIAL' in c), None) # RAZO SOCIAL
                col_sigla = next((c for c in df.columns if 'SIGLA' in c), None)
                col_ons = next((c for c in df.columns if 'CODIGO' in c or 'CDIGO' in c or 'CÓDIGO' in c), None)
                
                if not col_cnpj:
                    logger.error("Column CNPJ not found in Excel.")
                    break
                    
                raw_cnpj = row[col_cnpj]
                if pd.isna(raw_cnpj): continue
                
                # Clean CNPJ
                import re
                cnpj_clean = re.sub(r'[^0-9]', '', str(raw_cnpj))
                
                if not cnpj_clean: continue
                
                # Values
                nome = str(row[col_nome]).strip() if col_nome and not pd.isna(row[col_nome]) else None
                sigla = str(row[col_sigla]).strip() if col_sigla and not pd.isna(row[col_sigla]) else None
                cod_ons = str(row[col_ons]).strip() if col_ons and not pd.isna(row[col_ons]) else None
                
                # Find or Create
                transmissora = session.query(Transmissora).filter_by(cnpj=cnpj_clean).first()
                
                is_new = False
                if not transmissora:
                    transmissora = Transmissora(cnpj=cnpj_clean)
                    is_new = True
                    new_count += 1
                else:
                    updated_count += 1
                
                # Update fields
                if nome: transmissora.nome = nome
                if sigla: transmissora.sigla = sigla
                if cod_ons: transmissora.codigo_ons = cod_ons
                
                # Store full row as JSON
                import json
                row_dict = {}
                for k, v in row.items():
                    if pd.isna(v): 
                        row_dict[k] = None
                    else:
                        row_dict[k] = str(v)
                
                transmissora.dados_json = json.dumps(row_dict)
                transmissora.ultima_atualizacao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if is_new:
                    session.add(transmissora)
            
            session.commit()
            logger.info(f"Database update complete. New: {new_count}, Updated: {updated_count}")
            
        except Exception as e:
            logger.error(f"Error updating database: {e}")
            session.rollback()
        finally:
            session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True, help="AMSE Username")
    parser.add_argument("--password", required=True, help="AMSE Password")
    parser.add_argument("--output_dir", help="Output directory")
    parser.add_argument("--headless", action="store_true", help="Ignored (Requests)")
    parser.add_argument("--update-db", action="store_true", help="Update database after download")
    
    args = parser.parse_args()
    
    scraper = AmseScraper(output_dir=args.output_dir)
    file_path = scraper.login(args.user, args.password)
    
    if file_path and args.update_db:
        updater = AmseUpdater(DATABASE_URL)
        updater.process_file(file_path)
