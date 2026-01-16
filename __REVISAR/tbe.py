import requests
import os
import logging
import time
import json
import re
from bs4 import BeautifulSoup

# Diretórios de dados
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'Data')
TBE_JSON_PATH = os.path.join(DATA_DIR, 'empresas_tbe.json')
CNPJ_MAP_FILE = os.path.join(DATA_DIR, 'cnpj_mapping.json')
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\TUST\TBE"

# Configuração do logger
def setup_logger():
    """Configura e retorna o logger"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

logger = setup_logger()

def sanitize_name(name):
    """Remove caracteres inválidos para nomes de pastas e arquivos no Windows"""
    if not name:
        return "DESCONHECIDO"
    # Remove caracteres proibidos e limpa espaços extras/quebras de linha
    clean = re.sub(r'[<>:"/\\|?*]', '_', str(name))
    return " ".join(clean.split()).strip()

def carregar_empresas():
    try:
        if not os.path.exists(TBE_JSON_PATH):
            logger.error(f"Arquivo não encontrado: {TBE_JSON_PATH}")
            return []
        with open(TBE_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar {TBE_JSON_PATH}: {e}")
        return []

# Mapeamento fixo de CNPJs e siglas das transmissoras conhecidas
TRANSMISSORAS = {
    "03984987000114": {"sigla": "ECTE", "nome": "ECTE"},
    "04416923000260": {"sigla": "ETEP", "nome": "ETEP"},
    "04416935000295": {"sigla": "EATE", "nome": "EATE"},
    "04416935000376": {"sigla": "EATE", "nome": "EATE"},
    "05321920000206": {"sigla": "ERTE", "nome": "ERTE"},
    "05321987000321": {"sigla": "ENTE", "nome": "ENTE"},
    "05321987000240": {"sigla": "ENTE", "nome": "ENTE"},
    "05973734000170": {"sigla": "LUMITRANS", "nome": "LUMITRANS"},
    "07752818000100": {"sigla": "STC", "nome": "STC"},
    "10319371000275": {"sigla": "EBTE", "nome": "EBTE"},
    "11004138000266": {"sigla": "ESDE", "nome": "ESDE"},
    "14929924000262": {"sigla": "ETSE", "nome": "ETSE"},
    "24870962000240": {"sigla": "EDTE", "nome": "EDTE"},
    "26643937000250": {"sigla": "ESTE", "nome": "ESTE"},
    "26643937000330": {"sigla": "ESTE", "nome": "ESTE"},
}

CNPJ_BASE_MAP = {
    "03984987": "ECTE", "04416923": "ETEP", "04416935": "EATE",
    "05321920": "ERTE", "05321987": "ENTE", "05973734": "LUMITRANS",
    "07752818": "STC", "10319371": "EBTE", "11004138": "ESDE",
    "14929924": "ETSE", "24870962": "EDTE", "26643937": "ESTE",
}

def load_cnpj_mapping():
    if os.path.exists(CNPJ_MAP_FILE):
        try:
            with open(CNPJ_MAP_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception: pass
    return {}

def save_cnpj_mapping(mapping):
    try:
        with open(CNPJ_MAP_FILE, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=4, ensure_ascii=False)
    except Exception: pass

def get_transmissora_info(cnpj, nome_empresa):
    cnpj_mapping = load_cnpj_mapping()
    if cnpj in TRANSMISSORAS: return TRANSMISSORAS[cnpj]
    if cnpj in cnpj_mapping: return cnpj_mapping[cnpj]
    
    cnpj_base = cnpj[:8]
    if cnpj_base in CNPJ_BASE_MAP:
        sigla_base = CNPJ_BASE_MAP[cnpj_base]
        novo_mapeamento = {"sigla": sigla_base, "nome": sigla_base}
        cnpj_mapping[cnpj] = novo_mapeamento
        save_cnpj_mapping(cnpj_mapping)
        return novo_mapeamento
    
    sigla = sanitize_name(nome_empresa[:10].upper())
    novo_mapeamento = {"sigla": sigla, "nome": nome_empresa}
    cnpj_mapping[cnpj] = novo_mapeamento
    save_cnpj_mapping(cnpj_mapping)
    return novo_mapeamento

def login_tbe(usuario, senha):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    session = requests.Session()
    session.headers.update(headers)
    try:
        session.get("https://portalcliente.tbenergia.com.br/")
        login_data = {'Login': usuario, 'Senha': senha}
        response = session.post("https://portalcliente.tbenergia.com.br/Login/Index", data=login_data)
        if "Fechamento" in response.url: return session
    except Exception as e: logger.error(f"Erro no login: {e}")
    return None

def obter_notas_fiscais(session, codigo_ons):
    try:
        url = f"https://portalcliente.tbenergia.com.br/Fechamento/NotasRecentes?CNPJ={codigo_ons}"
        response = session.get(url)
        if response.status_code == 200 and 'Login' not in response.url: return response.text
    except Exception as e: logger.error(f"Erro ao obter notas: {e}")
    return None

def extrair_links_xml(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table', {'id': 'NfRecentes'})
    if not table: return []
    tbody = table.find('tbody')
    if not tbody: return []
    resultados = []
    for row in tbody.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 7: continue
        xml_link = None
        pdf_link = None
        for link in cells[-1].find_all('a'):
            txt = (link.text or '').upper()
            if 'XML' in txt: xml_link = link.get('href')
            elif 'PDF' in txt or 'DANFE' in txt: pdf_link = link.get('href')
        if xml_link:
            resultados.append({
                'competencia': cells[0].text.strip(),
                'nf_numero': cells[1].text.strip(),
                'empresa': cells[3].text.strip(),
                'cnpj_limpo': ''.join(filter(str.isdigit, cells[4].text)),
                'xml_link': xml_link,
                'pdf_link': pdf_link
            })
    return resultados

def baixar_arquivo(session, url, download_dir, filename, tipo):
    try:
        # Garante a criação da pasta antes do download
        os.makedirs(download_dir, exist_ok=True)
            
        if not url.startswith('http'):
            url = f"https://portalcliente.tbenergia.com.br{url}"
        response = session.get(url)
        if response.status_code == 200:
            # Sanitiza o nome do arquivo para evitar erros de sistema
            filename_clean = sanitize_name(filename)
            # Garante a extensão correta se a sanitização removeu
            if tipo == "XML" and not filename_clean.lower().endswith(".xml"): filename_clean += ".xml"
            if tipo == "PDF" and not filename_clean.lower().endswith(".pdf"): filename_clean += ".pdf"
            
            filepath = os.path.join(download_dir, filename_clean)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            logger.info(f"    ✓ {tipo} salvo: {filename_clean}")
            return True
    except Exception as e:
        logger.error(f"    ❌ Erro ao baixar {tipo} ({filename}): {e}")
    return False

def processar_todas():
    empresas = carregar_empresas()
    if not empresas: return

    for item in empresas:
        empresa_root = item['empresa']
        ons_code = item['codigo_ons']
        logger.info(f"\n--- Processando {empresa_root} - ONS {ons_code} ({item.get('nome', '')}) ---")
        
        session = login_tbe(item['usuario'], item['senha'])
        if not session:
            logger.error(f"Falha de login para ONS {ons_code}")
            continue
            
        html = obter_notas_fiscais(session, ons_code)
        if not html:
            logger.error(f"Não foi possível obter a lista de notas para ONS {ons_code}")
            continue
            
        notas = extrair_links_xml(html)
        if not notas:
            logger.info(f"Nenhuma nota encontrada para ONS {ons_code}")
            continue
            
        # Raiz da ONS no padrão ASSU
        ons_dir = os.path.join(BASE_DOWNLOAD_PATH, empresa_root, ons_code)
        
        for nota in notas:
            t_info = get_transmissora_info(nota['cnpj_limpo'], nota['empresa'])
            sigla = t_info['sigla']
            
            # Organização por Transmissora dentro da ONS
            dest_dir = os.path.join(ons_dir, sanitize_name(sigla))
            
            # Limpa a competência para evitar que vire subpasta (ex: 12/2024 -> 12_2024)
            comp_clean = sanitize_name(nota['competencia'])
            base_name = f"{sigla}_NF_{nota['nf_numero']}_{comp_clean}"
            
            # Download dos arquivos
            baixar_arquivo(session, nota['xml_link'], dest_dir, f"{base_name}.xml", "XML")
            
            pdf_url = nota['pdf_link'] or nota['xml_link'].replace('DownloadXml', 'DownloadPdf')
            baixar_arquivo(session, pdf_url, dest_dir, f"{base_name}.pdf", "PDF")
        
        time.sleep(1)

if __name__ == "__main__":
    try:
        logger.info("Iniciando Robô TBE")
        processar_todas()
        logger.info("Processo finalizado")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")