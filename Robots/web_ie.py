import os
import sys
import logging
import zipfile
import json
import requests
from io import BytesIO
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from base_robot import BaseRobot

class WebIERobot(BaseRobot):
    def __init__(self):
        super().__init__("web_ie")
        self.portal_base = "https://faturamento2.isaenergiabrasil.com.br"
        self.api_base = f"{self.portal_base}/api"
        self.portal_referer = f"{self.portal_base}/cteep/invoices"

    def _build_session(self) -> requests.Session:
        """Cria uma sessão com retries e timeouts razoáveis."""
        session = requests.Session()
        retries = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("HEAD", "GET", "OPTIONS", "POST"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _response_json_safe(self, resp: requests.Response):
        """Tenta fazer parse de JSON; quando falha, retorna None e loga detalhes úteis."""
        try:
            return resp.json()
        except requests.exceptions.JSONDecodeError:
            ctype = resp.headers.get("Content-Type", "<desconhecido>")
            snippet = (resp.text or "").strip()[:500]
            self.logger.error(
                f"Falha ao decodificar JSON. Status={resp.status_code}, Content-Type={ctype}, Corpo-inicio={snippet}"
            )
            return None

    def login_and_get_token(self, session: requests.Session, email: str, password: str) -> str:
        login_url = f"{self.api_base}/auth/login"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": self.portal_base,
            "Referer": self.portal_referer,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        # Pré-login
        try:
            _ = session.get(
                self.portal_referer,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "User-Agent": headers["User-Agent"],
                    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                }, timeout=20
            )
        except requests.RequestException:
            pass

        # CSRF cookie opcional
        xsrf_cookie = None
        for cname, cval in session.cookies.get_dict().items():
            if cname.upper().find("XSRF") >= 0 or cname.upper().find("CSRF") >= 0:
                xsrf_cookie = cval
                break

        login_headers = {**headers, "X-Requested-With": "XMLHttpRequest"}
        if xsrf_cookie:
            login_headers.setdefault("X-XSRF-TOKEN", xsrf_cookie)
            login_headers.setdefault("X-CSRF-TOKEN", xsrf_cookie)

        try:
            resp = session.post(login_url, json={"email": email, "password": password}, headers=login_headers, timeout=30)
        except requests.RequestException as exc:
            self.logger.error(f"Erro de rede durante o login: {exc}")
            raise

        if not resp.ok:
            self.logger.error(f"Login falhou. Status={resp.status_code} Corpo={(resp.text or '')[:200]}")
            return None

        data = self._response_json_safe(resp)
        if not isinstance(data, dict) or not data.get("accessToken"):
            self.logger.error("Resposta de login inválida ou sem accessToken.")
            return None

        return data["accessToken"]

    def fetch_and_download(self, session: requests.Session, token: str, dest_dir: str, date_start_str: str, date_end_str: str, date_start_obj: datetime):
        faturas_url = f"{self.api_base}/Invoice/search"
        headers_common = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": self.portal_base,
            "Referer": self.portal_referer,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        payload = {
            "currentPage": 1,
            "pageSize": 14,
            "term": "",
            "dateStart": date_start_str,
            "dateEnd": date_end_str,
            "invoiceType": "",
            "companyName": [],
            "onsCode": [],
            "isaCompany": [],
            "contract": [],
            "sortBy": "date",
            "sortDesc": False,
        }

        try:
            resp = session.post(faturas_url, json=payload, headers=headers_common, timeout=30)
        except requests.RequestException as exc:
            self.logger.error(f"Erro ao buscar faturas: {exc}")
            return 0
            
        if not resp.ok:
            self.logger.error(f"Falha ao buscar faturas. Status={resp.status_code} Corpo={(resp.text or '')[:200]}")
            return 0

        data = self._response_json_safe(resp) or {}
        total_pages = int(data.get("totalPages", 1) or 1)
        
        self.logger.info(f"Encontradas {total_pages} páginas de faturas.")

        download_url_base = f"{self.api_base}/Invoice/download/"
        download_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/zip",
            "Referer": f"{self.portal_referer}?currentPage=1&pageSize=12&sortBy=date&sortDesc=false",
            "User-Agent": headers_common["User-Agent"],
        }
        cookies = {"isa-fe-token": token}

        baixadas = 0
        for page in range(1, total_pages + 1):
            payload["currentPage"] = page
            try:
                resp = session.post(faturas_url, json=payload, headers=headers_common, timeout=30)
            except requests.RequestException as exc:
                self.logger.error(f"Erro de rede ao consultar página {page}: {exc}")
                continue
                
            if not resp.ok:
                self.logger.error(f"Falha ao buscar página {page} de faturas. Status={resp.status_code}")
                continue
                
            data = self._response_json_safe(resp) or {}
            for idx, fatura in enumerate(data.get("data", [])):
                invoice_id = fatura.get("invoiceId")
                if not invoice_id:
                    continue
                # Só baixa faturas do mês correto
                if not fatura.get("date", "").startswith(date_start_obj.strftime("%Y-%m")):
                    continue
                
                url = f"{download_url_base}{invoice_id}"
                self.logger.info(f"Baixando fatura ID: {invoice_id}...")
                
                try:
                    dresp = session.get(url, headers=download_headers, cookies=cookies, timeout=60)
                except requests.RequestException as exc:
                    self.logger.error(f"Erro de rede ao baixar fatura {invoice_id}: {exc}")
                    continue
                    
                if dresp.status_code == 200:
                    # Extrair para pasta única ou padronizada
                    # O script original criava subpastas. Vamos manter simples para o validador achar.
                    # Mas como pode ter multiplos arquivos, melhor extrair numa subpasta e o validador varre recursivamente.
                    extract_dir = os.path.join(dest_dir, f"fatura_{invoice_id}")
                    os.makedirs(extract_dir, exist_ok=True)
                    try:
                        with zipfile.ZipFile(BytesIO(dresp.content)) as zip_ref:
                            zip_ref.extractall(extract_dir)
                        self.logger.info(f"✅ Fatura {invoice_id} baixada e extraída em {extract_dir}")
                        baixadas += 1
                    except zipfile.BadZipFile:
                        self.logger.error(f"Arquivo ZIP da fatura {invoice_id} inválido/corrompido.")
                else:
                    self.logger.error(f"Erro ao baixar fatura {invoice_id}: {dresp.status_code}")
        return baixadas

    def run(self):
        email = self.args.user
        password = self.args.password
        
        if not email or not password:
            self.logger.error("Usuário (email) e senha são obrigatórios para este robô.")
            return

        # Lógica de Data (Mês Anterior ou Parametrizado)
        if self.args.competencia:
             # Formato esperado YYYYMM ou YYYY-MM
            try:
                comp = self.args.competencia.replace("-", "").replace("/", "")
                ano = int(comp[:4])
                mes = int(comp[4:6])
                date_start = datetime(ano, mes, 1)
                # Fim do mês 
                if mes == 12:
                    date_end = datetime(ano + 1, 1, 1) - timedelta(days=1)
                else:
                    date_end = datetime(ano, mes + 1, 1) - timedelta(days=1)
                
                self.logger.info(f"Competência forçada: {date_start.strftime('%m/%Y')}")
            except:
                self.logger.error(f"Formato de competência inválido: {self.args.competencia}. Use YYYYMM.")
                return
        else:
            # Padrão: Mês Anterior
            hoje = datetime.now()
            if hoje.month == 1:
                mes = 12
                ano = hoje.year - 1
            else:
                mes = hoje.month - 1
                ano = hoje.year
            
            date_start = datetime(ano, mes, 1)
            if mes == 12:
                date_end = datetime(ano + 1, 1, 1) - timedelta(days=1)
            else:
                date_end = datetime(ano, mes + 1, 1) - timedelta(days=1)

        date_start_str = date_start.strftime("%Y-%m-%dT00:00:00")
        date_end_str = date_end.strftime("%Y-%m-%dT00:00:00")
        
        output_dir = self.get_output_path()

        self.logger.info(f"Iniciando WebIE para {email} - Período: {date_start.strftime('%m/%Y')}")
        
        session = self._build_session()
        token = self.login_and_get_token(session, email, password)
        
        if token:
            baixadas = self.fetch_and_download(session, token, output_dir, date_start_str, date_end_str, date_start)
            self.logger.info(f"Processamento concluído. Total de faturas baixadas: {baixadas}")
        else:
            self.logger.error("Não foi possível autenticar.")

if __name__ == "__main__":
    bot = WebIERobot()
    bot.run()
