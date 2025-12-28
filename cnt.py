import requests
import os
from datetime import datetime
import json
import logging

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuração de diretórios
BASE_DIR_DOWNLOAD = r"C:\Users\Bruno\Downloads\TUST\CNT"

def carregar_empresas():
    """Carrega as informações das empresas do arquivo Data/empresas.json"""
    try:
        arquivo_json = os.path.join(os.path.dirname(__file__), 'Data', 'empresas.json')
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar empresas: {str(e)}")
        return {}

def baixar_xml_cnt(codigo_ons, empresa_nome, nome_ons):
    session = requests.Session()
    
    # 1. Primeiro acesso à página principal
    url_principal = "https://cntgo.com.br/faturas.html"
    headers_principal = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        logger.info(f"[{empresa_nome}] Acessando página principal para ONS {codigo_ons}...")
        session.get(url_principal, headers=headers_principal)
        
        # 2. Simular o envio do formulário (clique no botão BAIXAR)
        url_form = "https://cntgo.com.br/form.php"
        headers_form = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://cntgo.com.br",
            "Referer": "https://cntgo.com.br/faturas.html"
        }
        form_data = {"code": str(codigo_ons)}
        
        response_form = session.post(url_form, headers=headers_form, data=form_data)
        
        if response_form.status_code == 200 and response_form.content:
            # Caminho base igual ao da ASSU
            base_path = os.path.join(BASE_DIR_DOWNLOAD, empresa_nome, str(codigo_ons))
            os.makedirs(base_path, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"NFe_{nome_ons}_{timestamp}.xml"
            dest_path = os.path.join(base_path, nome_arquivo)
            
            with open(dest_path, "wb") as f:
                f.write(response_form.content)
            
            logger.info(f"[{empresa_nome}] XML baixado: {dest_path}")
            return True
        else:
            logger.error(f"[{empresa_nome}] Erro ao baixar para ONS {codigo_ons}: {response_form.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"[{empresa_nome}] Erro no processo: {str(e)}")
        return False

def main():
    empresas = carregar_empresas()
    if not empresas:
        logger.error("Empresas não carregadas.")
        return

    logger.info("Iniciando download dos XMLs CNT...")

    for empresa_nome, codigos_dict in empresas.items():
        logger.info(f"\n=== Empresa: {empresa_nome} ===")
        for codigo_ons, nome_ons in codigos_dict.items():
            baixar_xml_cnt(codigo_ons, empresa_nome, nome_ons)

    logger.info("\nProcessamento concluído!")

if __name__ == "__main__":
    main()
