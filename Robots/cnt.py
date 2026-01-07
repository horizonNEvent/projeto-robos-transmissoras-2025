import requests
import os
from datetime import datetime
import json
import logging
import argparse

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuração de diretórios
def get_base_download_path():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base = os.environ.get("TUST_DOWNLOADS_BASE", os.path.join(root, "downloads"))
    return os.path.join(base, "TUST", "CNT")

BASE_DIR_DOWNLOAD = get_base_download_path()

def carregar_empresas():
    """Carrega as informações das empresas do arquivo Data/empresas.json"""
    try:
        arquivo_json = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Data', 'empresas.json')
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar empresas: {str(e)}")
        return {}

def baixar_xml_cnt(codigo_ons, empresa_nome, nome_ons, output_dir=None):
    import time
    import random
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    # Pequeno delay aleatório para evitar detecção (Simula humano)
    time.sleep(random.uniform(1.5, 4.0))

    base_dir = output_dir or BASE_DIR_DOWNLOAD
    session = requests.Session()
    
    # Configuração de Retry (Tenta 3 vezes em caso de queda de conexão)
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504], raise_on_status=False)
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
    url_principal = "https://cntgo.com.br/faturas.html"
    headers_principal = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive"
    }
    
    try:
        logger.info(f"[{empresa_nome}] Acessando página principal para ONS {codigo_ons}...")
        session.get(url_principal, headers=headers_principal, timeout=20)
        
        # 2. Simular o envio do formulário
        url_form = "https://cntgo.com.br/form.php"
        headers_form = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://cntgo.com.br",
            "Referer": "https://cntgo.com.br/faturas.html",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        }
        form_data = {"code": str(codigo_ons)}
        
        response_form = session.post(url_form, headers=headers_form, data=form_data, timeout=30)
        
        if response_form.status_code == 200 and response_form.content:
            if len(response_form.content) < 100:
                logger.error(f"[{empresa_nome}] Arquivo muito pequeno/vazio para ONS {codigo_ons}.")
                return False

            base_path = os.path.join(base_dir, empresa_nome, str(codigo_ons))
            os.makedirs(base_path, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"NFe_{nome_ons}_{timestamp}.xml".replace(" ", "_")
            dest_path = os.path.join(base_path, nome_arquivo)
            
            with open(dest_path, "wb") as f:
                f.write(response_form.content)
            
            logger.info(f"[{empresa_nome}] XML baixado: {dest_path}")
            return True
        else:
            logger.error(f"[{empresa_nome}] Erro ao baixar (Cod: {response_form.status_code})")
            return False
            
    except Exception as e:
        logger.error(f"[{empresa_nome}] Erro de conexão/processo: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--empresa", help="Nome da empresa para filtrar")
    parser.add_argument("--agente", help="Código ONS do agente para filtrar")
    parser.add_argument("--output_dir", help="Pasta de destino dos downloads")
    args = parser.parse_args()

    empresas = carregar_empresas()
    if not empresas:
        logger.error("Empresas não carregadas.")
        return

    logger.info("Iniciando download dos XMLs CNT...")

    for empresa_nome, codigos_dict in empresas.items():
        # Filtro de Empresa (Case Insensitive e remove espaços)
        if args.empresa and args.empresa.strip().upper() != empresa_nome.strip().upper():
            continue

        logger.info(f"\n=== Empresa: {empresa_nome} ===")
        
        # Prepara lista de agentes se houver filtro
        filtro_agentes = []
        if args.agente:
            filtro_agentes = [a.strip() for a in str(args.agente).split(',')]

        for codigo_ons, nome_ons in codigos_dict.items():
            # Filtro de Agente (Suporta lista separada por vírgula)
            if filtro_agentes and str(codigo_ons).strip() not in filtro_agentes:
                continue
            baixar_xml_cnt(codigo_ons, empresa_nome, nome_ons, output_dir=args.output_dir)

    logger.info("\nProcessamento concluído!")

if __name__ == "__main__":
    main()
