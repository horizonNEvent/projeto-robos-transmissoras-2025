import argparse
import logging
import os
import re
import time
import requests
from bs4 import BeautifulSoup
import urllib.parse
import html

# Import BaseRobot
try:
    from Robots.base_robot import BaseRobot
except ImportError:
    # Fallback for local testing if running from Robots/ directly
    from base_robot import BaseRobot

class EletrobrasRobot(BaseRobot):
    """
    Robô para Eletrobras (Portal do Cliente).
    """
    def __init__(self):
        super().__init__("eletrobras")
        self.base_url = "https://portaldocliente.eletrobras.com/sap/bc/webdynpro/sap/zwda_portalclientes"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        })
        self.sap_context_id = None
        self.sap_wd_secure_id = None
        self.current_html = None

    def _unpack_delta_html(self, raw_html):
        """Extracts HTML content from SAP Delta XML/CDATA"""
        if "<![CDATA[" in raw_html:
            cdatas = re.findall(r'<!\[CDATA\[(.*?)\]\]>', raw_html, re.DOTALL)
            if cdatas:
                return max(cdatas, key=len)
        return raw_html

    def _extract_sap_ids(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        form = soup.find('form', {'name': 'sap.client.SsrClient.form'})
        if form and form.get('action'):
            action = form.get('action')
            match = re.search(r'sap-contextid=([^&]+)', action)
            if match:
                self.sap_context_id = match.group(1)
        
        inp_sec = soup.find('input', {'id': 'sap-wd-secure-id'})
        if inp_sec and inp_sec.get('value'):
            self.sap_wd_secure_id = inp_sec.get('value')

    def login(self):
        username = self.args.user
        password = self.args.password

        if not username or not password:
            self.logger.error("Credenciais não fornecidas (--user e --password obrigatórios).")
            return False

        self.logger.info(f"Logging in as {username}...")
        
        try:
            resp_init = self.session.get(f"{self.base_url}?sap-client=130&sap-theme=sap_bluecrystal")
            self.current_html = resp_init.text
            self._extract_sap_ids(self.current_html)
        except Exception as e:
            self.logger.error(f"Connection Error: {e}")
            return False

        if not self.sap_context_id or not self.sap_wd_secure_id:
            self.logger.error("Failed to extract SAP IDs.")
            return False

        # Handshake
        url_action = f"{self.base_url}?sap-contextid={self.sap_context_id}"
        body_handshake = f"sap-charset=utf-8&sap-wd-secure-id={self.sap_wd_secure_id}&SAPEVENTQUEUE=ClientInspector_Notify~E002Id~E004WD01~E005Data~E004ClientWidth~003A1920px~003BClientHeight~003A644px~003BScreenWidth~003A1920px~003BScreenHeight~003A1080px~003BScreenOrientation~003Alandscape~003BThemedFormLayoutRowHeight~003A27px~003BDeviceType~003ADESKTOP~E003~E002ResponseData~E004delta~E005EnqueueCardinality~E004single~E003~E002~E003~E001Custom_ClientInfos~E002Id~E004WD01~E005WindowOpenerExists~E004false~E005ClientURL~E004https~003A~002F~002Fportaldocliente.furnas.com.br~002Fsap~002Fbc~002Fwebdynpro~002Fsap~002Fzwda_portalclientes~003Fsap-client~003D130~0026sap-theme~003Dsap_bluecrystal~0023~E005ClientWidth~E0041920~E005ClientHeight~E004644~E005DocumentDomain~E004furnas.com.br~E005IsTopWindow~E004true~E005ParentAccessible~E004true~E003~E002ClientAction~E004enqueue~E005ResponseData~E004delta~E003~E002~E003~E001LoadingPlaceHolder_Load~E002Id~E004_loadingPlaceholder_~E003~E002ResponseData~E004delta~E005ClientAction~E004submit~E003~E002~E003"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        resp_handshake = self.session.post(url_action, data=body_handshake, headers=headers)
        
        handshake_html = self._unpack_delta_html(resp_handshake.text)
        soup_hs = BeautifulSoup(handshake_html, 'html.parser')
        entrar_span = soup_hs.find('span', string=re.compile("Entrar"))
        btn_id = "WD39"
        if entrar_span:
            parent = entrar_span.find_parent()
            if parent and parent.get('id'):
                btn_id = parent.get('id')

        user_hex = username.replace("@", "~0040")
        
        login_queue = (
            f"ComboBox_Change~E002Id~E004WD2C~E005Value~E004{user_hex}~E003~E002ResponseData~E004delta~E005EnqueueCardinality~E004single~E005Delay~E004full~E003~E002~E003"
            f"~E001InputField_Change~E002Id~E004WD32~E005Value~E004{password}~E003~E002ResponseData~E004delta~E005EnqueueCardinality~E004single~E005Delay~E004full~E003~E002~E003"
            f"~E001ClientInspector_Notify~E002Id~E004WD01~E005Data~E004ClientHeight~003A457px~E003~E002ResponseData~E004delta~E005EnqueueCardinality~E004single~E003~E002~E003"
            f"~E001Button_Press~E002Id~E004{btn_id}~E003~E002ResponseData~E004delta~E005ClientAction~E004submit~E003~E002~E003"
        )
        
        body_login = f"sap-charset=utf-8&sap-wd-secure-id={self.sap_wd_secure_id}&_stateful_=X&SAPEVENTQUEUE={login_queue}"
        resp_login = self.session.post(url_action, data=body_login, headers=headers)
        self.current_html = self._unpack_delta_html(resp_login.text)

        if "Logoff" in self.current_html or "lsTbsPanel2" in self.current_html or "Boleto" in self.current_html or "Alterar Senha" in self.current_html:
            self.logger.info("Login Successful!")
            return True
        else:
            self.logger.error("Login Failed.")
            return False

    def get_tabs(self):
        soup = BeautifulSoup(self.current_html, 'html.parser')
        tabs = []
        tab_panel_id = None
        
        tablist = soup.find('div', {'role': 'tablist'})
        if tablist:
            raw_id = tablist.get('id')
            if raw_id:
                tab_panel_id = raw_id.replace('-panel', '').replace('-content', '')
            
            tab_items = tablist.find_all('div', {'ct': 'TSITM'})
            for idx, item in enumerate(tab_items):
                lsdata = item.get('lsdata', '')
                t_id = item.get('id')
                
                span = item.find('span', {'role': 'tab'})
                t_text = span.get_text(separator=' ', strip=True) if span else "Unknown"
                if span and span.find('div'):
                    span.div.extract()
                    t_text = span.get_text(separator=' ', strip=True)
                
                index_match = re.search(r"1:(\d+)", lsdata)
                if index_match:
                    t_index = int(index_match.group(1))
                else:
                    t_index = idx 
                
                tabs.append({'id': t_id, 'text': t_text, 'index': t_index})
        return tab_panel_id, tabs

    def select_tab(self, tab_panel_id, tab_id, tab_index):
        self.logger.info(f"Switching to tab: {tab_id} (Index: {tab_index})...")
        url_action = f"{self.base_url}?sap-contextid={self.sap_context_id}"
        event_queue = (
            f"TabStrip_TabSelect~E002Id~E004{tab_panel_id}~E005ItemId~E004{tab_id}~E005ItemIndex~E004{tab_index}"
            f"~E003~E002ResponseData~E004delta~E005ClientAction~E004submit~E003~E002~E003"
        )
        body = f"sap-charset=utf-8&sap-wd-secure-id={self.sap_wd_secure_id}&_stateful_=X&SAPEVENTQUEUE={event_queue}"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        resp = self.session.post(url_action, data=body, headers=headers)
        self.current_html = self._unpack_delta_html(resp.text)
        return True

    def parse_table(self):
        soup = BeautifulSoup(self.current_html, 'html.parser')
        if soup.find(string="A tabela não contém dados"):
            self.logger.info("Table is empty.")
            return []

        rows = soup.find_all('tr', {'sst': '0'})
        data = []
        for row in rows:
            cols = row.find_all('td')
            col_texts = [c.get_text(strip=True) for c in cols]
            
            def get_btn_id(col_index):
                if col_index < len(cols):
                    a_tag = cols[col_index].find('a')
                    if a_tag: return a_tag.get('id')
                return None
            
            xml_btn = None
            boleto_btn = None
            fatura_btn = None
            
            if len(cols) > 12:
                 xml_btn = get_btn_id(12)
                 fatura_btn = get_btn_id(2)
                 boleto_btn = get_btn_id(3)

            data.append({
                'col_values': col_texts,
                'xml_btn_id': xml_btn,
                'fatura_btn_id': fatura_btn,
                'boleto_btn_id': boleto_btn
            })
        return data

    def download_file(self, button_id, output_filename, max_retries=3):
        for attempt in range(1, max_retries + 1):
            self.logger.info(f"Downloading {output_filename} (Attempt {attempt}/{max_retries})")
            try:
                url_action = f"{self.base_url}?sap-contextid={self.sap_context_id}"
                event_queue = (
                    f"Button_Press~E002Id~E004{button_id}"
                    f"~E003~E002ResponseData~E004delta~E005ClientAction~E004submit~E003~E002~E003"
                )
                body = f"sap-charset=utf-8&sap-wd-secure-id={self.sap_wd_secure_id}&_stateful_=X&SAPEVENTQUEUE={event_queue}"
                headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                resp = self.session.post(url_action, data=body, headers=headers, stream=True)
                
                content_type = resp.headers.get('Content-Type', '')
                if 'text/xml' in content_type or 'text/html' in content_type:
                    text_decoded = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), resp.text)
                    download_url = None
                    
                    match = re.search(r'"url":"([^"]+)"', text_decoded)
                    if match: download_url = match.group(1)
                    if not download_url:
                        match = re.search(r'(https?://[^"]*sap-wd-filedownload[^"]*)', text_decoded)
                        if match: download_url = match.group(1)
                    if not download_url:
                        match = re.search(r'(/sap/bc/webdynpro/[^"]*sap-wd-filedownload[^"]*)', text_decoded)
                        if match: download_url = match.group(1)

                    if download_url:
                        download_url = download_url.replace('~003A', ':').replace('~002F', '/').replace('~003F', '?').replace('~003D', '=').replace('~0026', '&')
                        if '"' in download_url: download_url = download_url.split('"')[0]
                        if download_url.startswith('/'): download_url = "https://portaldocliente.eletrobras.com" + download_url
                        
                        file_resp = self.session.get(download_url, stream=True)
                        if file_resp.status_code == 200:
                            with open(output_filename, 'wb') as f:
                                for chunk in file_resp.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            self.logger.info(f"SUCCESS: Saved {output_filename}")
                            return True
                else:
                    with open(output_filename, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    self.logger.info(f"SUCCESS: Saved (Direct) {output_filename}")
                    return True
            except Exception as e:
                self.logger.error(f"Download Error: {e}")
            
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        return False

    def run(self):
        if not self.login():
            return

        base_output = self.get_output_path()
        tab_panel_id, tabs = self.get_tabs()
        self.logger.info(f"Found {len(tabs)} tabs.")

        for t in tabs:
            if "Transmissão" in t['text']: # Match Logic
                self.logger.info(f"Processing Tab: {t['text']}")
                if self.select_tab(tab_panel_id, t['id'], t['index']):
                    data = self.parse_table()
                    self.logger.info(f"Found {len(data)} rows.")
                    
                    for row in data:
                        fatura_num_raw = row['col_values'][5] if len(row['col_values']) > 5 else "unknown"
                        fatura_num = fatura_num_raw.replace('/', '-').replace('\\', '-').strip()
                        
                        if not fatura_num or fatura_num == "unknown":
                             continue
                        
                        target_dir = os.path.join(base_output, fatura_num)
                        os.makedirs(target_dir, exist_ok=True)
                        
                        if row['xml_btn_id']:
                             fname = os.path.join(target_dir, f"NF_{fatura_num}.xml")
                             if not os.path.exists(fname): self.download_file(row['xml_btn_id'], fname)
                        
                        if row['boleto_btn_id']:
                             fname = os.path.join(target_dir, f"Boleto_{fatura_num}.pdf")
                             if not os.path.exists(fname): self.download_file(row['boleto_btn_id'], fname)
                                 
                        if row['fatura_btn_id']:
                             fname = os.path.join(target_dir, f"Fatura_{fatura_num}.pdf")
                             if not os.path.exists(fname): self.download_file(row['fatura_btn_id'], fname)

if __name__ == "__main__":
    robot = EletrobrasRobot()
    robot.run()
