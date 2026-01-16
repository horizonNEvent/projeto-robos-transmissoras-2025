import os
import sys
import logging
import zipfile
from io import BytesIO
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import json

# Optional: load .env if python-dotenv is installed
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# 1. Calcular o mês anterior ao atual
hoje = datetime.now()
if hoje.month == 1:
    mes = 12
    ano = hoje.year - 1
else:
    mes = hoje.month - 1
    ano = hoje.year

# Primeiro e último dia do mês anterior
date_start = datetime(ano, mes, 1)
if mes == 12:
    date_end = datetime(ano + 1, 1, 1) - timedelta(days=1)
else:
    date_end = datetime(ano, mes + 1, 1) - timedelta(days=1)

date_start_str = date_start.strftime("%Y-%m-%dT00:00:00")
date_end_str = date_end.strftime("%Y-%m-%dT00:00:00")
mes_ano_str = date_start.strftime("%m_%Y")  # Para nomear a pasta

print(f"Buscando faturas de {date_start.strftime('%m/%Y')}")


# --- Configuração de logging / debug ---
DEBUG = os.getenv("DEBUG", "0") == "1"
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)


def _build_session() -> requests.Session:
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


def _response_json_safe(resp: requests.Response):
    """Tenta fazer parse de JSON; quando falha, retorna None e loga detalhes úteis."""
    try:
        return resp.json()
    except requests.exceptions.JSONDecodeError:
        ctype = resp.headers.get("Content-Type", "<desconhecido>")
        snippet = (resp.text or "").strip()[:500]
        logging.error(
            "Falha ao decodificar JSON. Status=%s, Content-Type=%s, Corpo-inicio=%.120s",
            resp.status_code,
            ctype,
            snippet,
        )
        return None

########################################
# Suporte a múltiplas contas/empresas  #
########################################

portal_base = "https://faturamento2.isaenergiabrasil.com.br"
api_base = f"{portal_base}/api"
portal_referer = f"{portal_base}/cteep/invoices"

def load_credentials():
    """Carrega credenciais de Data/empresas.cteep.json e organiza para o padrão da ASSU."""
    output_root = r"C:\Users\Bruno\Downloads\TUST\ISA"
    cred_path = os.path.join(os.path.dirname(__file__), "Data", "empresas.cteep.json")
    accounts = []

    if os.path.exists(cred_path):
        try:
            with open(cred_path, "r", encoding="utf-8") as f:
                dados = json.load(f)
            
            # Mapeia as empresas do JSON para o formato esperado pelo script
            for item in dados:
                email = item.get("usuario", "").strip()
                password = item.get("senha", "").strip()
                company = item.get("empresa", "").strip()
                codigo_ons = item.get("codigo_ons", "").strip()
                
                if email and password:
                    accounts.append({
                        "email": email,
                        "password": password,
                        "company": company,
                        "codigo_ons": codigo_ons,
                        "subfolders": [company, codigo_ons] # Padrão igual ao da ASSU
                    })
            
            if DEBUG:
                logging.debug("Credenciais carregadas de %s; contas=%d", cred_path, len(accounts))
        except Exception as e:
            logging.error("Falha ao ler %s: %s", cred_path, e)

    if not accounts:
        logging.error("Credenciais ausentes em %s.", cred_path)
        sys.exit(1)

    return output_root, accounts

    if not accounts:
        logging.error("Credenciais ausentes. Configure credentials.json (recomendado) ou variáveis de ambiente.")
        sys.exit(1)

    return output_root, accounts


def ensure_output_dir(output_root: str, account: dict) -> str:
    # subfolders pode ser string "AE/SJP" ou lista ["AE", "SJP"]
    sub = account.get("subfolders")
    parts = []
    if isinstance(sub, str) and sub:
        parts = [p for p in sub.replace("\\", "/").split("/") if p]
    elif isinstance(sub, list) and sub:
        parts = [str(p) for p in sub if str(p)]
    else:
        parts = [account.get("company", "AE")]  # padrão: apenas a empresa

    pasta_raiz = os.path.join(output_root, *parts)
    pasta_destino = os.path.join(pasta_raiz, mes_ano_str)
    os.makedirs(pasta_destino, exist_ok=True)
    return pasta_destino


def login_and_get_token(session: requests.Session, email: str, password: str) -> str:
    login_url = f"{api_base}/auth/login"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": portal_base,
        "Referer": portal_referer,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    # Pré-login
    try:
        _ = session.get(
            portal_referer,
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
        logging.exception("Erro de rede durante o login: %s", exc)
        raise

    if not resp.ok:
        logging.error("Login falhou. Status=%s Corpo=%.200s", resp.status_code, (resp.text or "")[:200])
        raise SystemExit(1)

    data = _response_json_safe(resp)
    if not isinstance(data, dict) or not data.get("accessToken"):
        dump_path = os.path.join(os.path.dirname(__file__), "login_failed.html")
        try:
            with open(dump_path, "w", encoding="utf-8") as f:
                f.write(resp.text)
        except Exception:
            pass
        logging.error("Resposta de login inválida. Conteúdo salvo em: %s", dump_path)
        raise SystemExit(1)

    return data["accessToken"]


def fetch_and_download(session: requests.Session, token: str, dest_dir: str):
    faturas_url = f"{api_base}/Invoice/search"
    headers_common = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": portal_base,
        "Referer": portal_referer,
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
        logging.exception("Erro ao buscar faturas: %s", exc)
        raise SystemExit(1)
    if not resp.ok:
        logging.error("Falha ao buscar faturas. Status=%s Corpo=%.200s", resp.status_code, (resp.text or "")[:200])
        raise SystemExit(1)

    data = _response_json_safe(resp) or {}
    total_pages = int(data.get("totalPages", 1) or 1)

    download_url_base = f"{api_base}/Invoice/download/"
    download_headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/zip",
        "Referer": f"{portal_referer}?currentPage=1&pageSize=12&sortBy=date&sortDesc=false",
        "User-Agent": headers_common["User-Agent"],
    }
    cookies = {"isa-fe-token": token}

    baixadas = 0
    for page in range(1, total_pages + 1):
        payload["currentPage"] = page
        try:
            resp = session.post(faturas_url, json=payload, headers=headers_common, timeout=30)
        except requests.RequestException as exc:
            logging.error("Erro de rede ao consultar página %s: %s", page, exc)
            continue
        if not resp.ok:
            logging.error("Falha ao buscar página %s de faturas. Status=%s", page, resp.status_code)
            continue
        data = _response_json_safe(resp) or {}
        for idx, fatura in enumerate(data.get("data", [])):
            invoice_id = fatura.get("invoiceId")
            if not invoice_id:
                continue
            # Só baixa faturas do mês correto
            if not fatura.get("date", "").startswith(date_start.strftime("%Y-%m")):
                continue
            url = f"{download_url_base}{invoice_id}"
            try:
                dresp = session.get(url, headers=download_headers, cookies=cookies, timeout=60)
            except requests.RequestException as exc:
                logging.error("Erro de rede ao baixar fatura %s: %s", invoice_id, exc)
                continue
            if dresp.status_code == 200:
                extract_dir = os.path.join(dest_dir, f"fatura_{invoice_id}_p{page}_i{idx}")
                os.makedirs(extract_dir, exist_ok=True)
                try:
                    with zipfile.ZipFile(BytesIO(dresp.content)) as zip_ref:
                        zip_ref.extractall(extract_dir)
                    baixadas += 1
                except zipfile.BadZipFile:
                    logging.error("Arquivo ZIP da fatura %s inválido/corrompido.", invoice_id)
            else:
                logging.error("Erro ao baixar fatura %s: %s", invoice_id, dresp.status_code)
    return baixadas


def main():
    output_root, accounts = load_credentials()
    total_baixadas_geral = 0
    for acc in accounts:
        email = acc["email"]; password = acc["password"]
        company = acc.get("company", "AE")
        print(f"[Empresa: {company}] Iniciando processamento {date_start.strftime('%m/%Y')}...")
        dest_dir = ensure_output_dir(output_root, acc)
        session = _build_session()
        token = login_and_get_token(session, email, password)
        baixadas = fetch_and_download(session, token, dest_dir)
        print(f"[Empresa: {company}] Extração concluída. Total extraídas: {baixadas}")
        total_baixadas_geral += baixadas
    print(f"Extração de todas as faturas de {date_start.strftime('%m/%Y')} concluída. Total geral extraídas: {total_baixadas_geral}")


if __name__ == "__main__":
    main()