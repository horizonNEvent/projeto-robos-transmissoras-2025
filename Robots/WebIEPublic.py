import requests
import json
import os
import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin
from io import BytesIO
import zipfile
import sqlite3

from base_robot import BaseRobot
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Configurações de Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'Data')
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(ROOT_DIR, 'sql_app.db')

def sanitize_name(name):
    """Remove caracteres perigosos para nome de pasta."""
    if not name:
        return "DESCONHECIDO"
    import re
    clean = re.sub(r'[<>:"/\\|?*]', '_', str(name))
    return " ".join(clean.split()).strip()


def carregar_targets():
    """Carrega lista de transmissoras do Banco de Dados (SQLite)."""
    targets = {}
    try:
        if not os.path.exists(DB_PATH):
            print(f"[AVISO] Banco de dados não encontrado: {DB_PATH}")
            return {}

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Tenta carregar de tabela específica se existir
        try:
            cursor.execute("SELECT codigo_ons, nome FROM ie_public_targets WHERE ativo = 1")
            rows = cursor.fetchall()
            if rows:
                for row in rows:
                    targets[str(row[0])] = row[1]
                conn.close()
                print(f"Carregados {len(targets)} alvos da tabela ie_public_targets.")
                return targets
        except:
            pass

        # Fallback: tenta tabela siget_public_targets (se compartilharem)
        try:
            cursor.execute("SELECT codigo_ons, nome FROM siget_public_targets WHERE ativo = 1")
            rows = cursor.fetchall()
            for row in rows:
                targets[str(row[0])] = row[1]
        except:
            pass

        conn.close()
        if targets:
            print(f"Carregados {len(targets)} alvos do banco de dados.")
    except Exception as e:
        print(f"Erro ao ler banco de dados: {e}")
    return targets


class WebIEPublicRobot(BaseRobot):
    """
    Robot que acessa múltiplas transmissoras no portal WebIE de forma pública.
    Parametrizado por ons_code e ons_name para iteração em lote.
    """

    def __init__(self, ons_code, ons_name, email=None, password=None, output_dir=None):
        super().__init__("WebIEPublic")
        self.ons_code = ons_code
        self.ons_name = ons_name
        self.email = email
        self.password = password

        # Portal WebIE
        self.portal_base = "https://faturamento2.isaenergiabrasil.com.br"
        self.api_base = f"{self.portal_base}/api"
        self.portal_referer = f"{self.portal_base}/cteep/invoices"

        # Pasta de saída parametrizada
        safe_ons_name = sanitize_name(self.ons_name)
        folder_name = f"EMC_{self.ons_code}_{safe_ons_name}"

        if output_dir:
            self.output_path = os.path.join(output_dir, folder_name)
        else:
            base = os.environ.get("TUST_DOWNLOADS_BASE", os.path.join(ROOT_DIR, "downloads"))
            self.output_path = os.path.join(base, "TUST", "WEBIEPUBLIC", folder_name)

        os.makedirs(self.output_path, exist_ok=True)

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
        """Efetua login e obtém token de acesso."""
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
            return None

        if not resp.ok:
            self.logger.error(f"Login falhou. Status={resp.status_code} Corpo={(resp.text or '')[:200]}")
            return None

        data = self._response_json_safe(resp)
        if not isinstance(data, dict) or not data.get("accessToken"):
            self.logger.error("Resposta de login inválida ou sem accessToken.")
            return None

        return data["accessToken"]

    def fetch_and_download(self, session: requests.Session, token: str, date_start_str: str, date_end_str: str, date_start_obj: datetime) -> int:
        """Busca e baixa faturas para a transmissora configurada."""
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
                    extract_dir = os.path.join(self.output_path, f"fatura_{invoice_id}")
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

    def processar(self, email=None, password=None, competencia=None):
        """Processa downloads para a transmissora configurada."""
        email = email or self.email
        password = password or self.password

        if not email or not password:
            self.logger.error("Email e senha são obrigatórios para autenticação WebIE.")
            return 0

        # Lógica de Data (Mês Anterior ou Parametrizado)
        if competencia:
            try:
                comp = competencia.replace("-", "").replace("/", "")
                ano = int(comp[:4])
                mes = int(comp[4:6])
                date_start = datetime(ano, mes, 1)
                # Fim do mês
                if mes == 12:
                    date_end = datetime(ano + 1, 1, 1) - timedelta(days=1)
                else:
                    date_end = datetime(ano, mes + 1, 1) - timedelta(days=1)

                self.logger.info(f"Competência forçada: {date_start.strftime('%m/%Y')}")
            except Exception as e:
                self.logger.error(f"Formato de competência inválido: {competencia}. Use YYYYMM. Erro: {e}")
                return 0
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

        self.logger.info(f"[WebIEPublic] Transmissora: {self.ons_code} ({self.ons_name}) - Período: {date_start.strftime('%m/%Y')}")

        session = self._build_session()
        token = self.login_and_get_token(session, email, password)

        if token:
            baixadas = self.fetch_and_download(session, token, date_start_str, date_end_str, date_start)
            self.logger.info(f"[WebIEPublic] Processamento concluído para {self.ons_code}. Total: {baixadas} faturas.")
            return baixadas
        else:
            self.logger.error(f"[WebIEPublic] Não foi possível autenticar para transmissora {self.ons_code}")
            return 0

    def run(self):
        """Executa o robot com parâmetros de linha de comando."""
        import argparse
        parser = argparse.ArgumentParser(description="WebIEPublic Robot - Múltiplas Transmissoras")
        parser.add_argument("--empresa", type=str, help="Compatível com gerenciador / RobotConfig (ignorado)")
        parser.add_argument("--agente", type=str, help="Compatível com gerenciador / RobotConfig (ignorado)")
        parser.add_argument("--user", type=str, help="Email para autenticação WebIE")
        parser.add_argument("--password", type=str, help="Senha para autenticação WebIE")
        parser.add_argument("--competencia", type=str, help="Competência YYYYMM (Opcional)")
        parser.add_argument("--output_dir", help="Pasta de destino dos downloads")
        parser.add_argument("--headless", action="store_true", help="Executar em modo headless (ignorado)")

        args = parser.parse_args()
        targets = carregar_targets()

        if not targets:
            self.logger.error("Nenhuma transmissora carregada do banco de dados.")
            return

        email = args.user
        password = args.password

        if not email or not password:
            self.logger.error("Email (--user) e Senha (--password) são obrigatórios para WebIEPublic.")
            return

        self.logger.info(f"Iniciando WebIEPublic para {len(targets)} transmissoras (Email: {email}, Comp: {args.competencia or 'AUTO'})...")

        total_baixadas = 0
        for trans_code, trans_name in targets.items():
            bot = WebIEPublicRobot(trans_code, trans_name, email, password, output_dir=args.output_dir)
            baixadas = bot.processar(email, password, args.competencia)
            total_baixadas += baixadas

        self.logger.info(f"WebIEPublic: Processamento concluído. Total geral: {total_baixadas} faturas de {len(targets)} transmissoras.")


if __name__ == "__main__":
    bot = WebIEPublicRobot("0000", "TESTE")
    bot.run()
