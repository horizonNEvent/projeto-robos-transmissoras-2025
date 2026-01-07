import requests
import json
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Configurações de Diretórios
# Configurações de Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'Data') # Ajuste para pasta Data na raiz
EMPRESAS_JSON_PATH = os.path.join(DATA_DIR, 'empresas.json')
from utils_paths import get_base_download_path, ensure_dir
BASE_DIR_DEFAULT = get_base_download_path("WEBETTM")

def carregar_empresas():
    try:
        if not os.path.exists(EMPRESAS_JSON_PATH):
            return {}
        with open(EMPRESAS_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def sanitize_name(name):
    if not name: return "DESCONHECIDO"
    clean = re.sub(r'[<>:"/\\|?*]', '_', str(name))
    return " ".join(clean.split()).strip()

class ETTMRobot:
    def __init__(self, empresa_nome, ons_code, ons_name, output_dir=None):
        self.empresa_nome = empresa_nome
        self.ons_code = ons_code
        self.ons_name = ons_name
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }
        # Estrutura padrão: TUST / WebETTM / EMC_XXXX_Nome
        safe_ons_name = sanitize_name(self.ons_name)
        folder_name = f"EMC_{self.ons_code}_{safe_ons_name}"
        self.output_path = os.path.join(output_dir or BASE_DIR_DEFAULT, folder_name)
        
        ensure_dir(self.output_path)

    def baixar_arquivo(self, url, filename, tipo):
        try:
            full_url = urljoin("https://sys.sigetplus.com.br", url)
            res = self.session.get(full_url, headers=self.headers, timeout=30)
            if res.status_code == 200:
                with open(filename, 'wb') as f:
                    f.write(res.content)
                print(f"       [OK] {tipo} salvo.")
                return True
            else:
                print(f"       [ERRO] HTTP {res.status_code} em {tipo}")
        except Exception as e:
            print(f"       [ERRO] Download {tipo}: {e}")
        return False

    def processar(self):
        print(f"\n>>> [ETTM] ONS: {self.ons_code} ({self.ons_name})")
        
        # O ETTM parece ser um endpoint público ou sem login complexo do SigetPlus para transmissora 1311?
        # A URL original era .../transmitter/1311/invoices?agent={ons_code}
        url = f"https://sys.sigetplus.com.br/cobranca/transmitter/1311/invoices?agent={self.ons_code}"
        
        try:
            res = self.session.get(url, headers=self.headers, timeout=30)
            if res.status_code != 200:
                print(f"    [ERRO] Falha ao acessar página: {res.status_code}")
                return

            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Verificar se a página retornou algo útil ou se está vazia/erro
            if "Nenhuma fatura encontrada" in res.text:
                 print(f"    [AVISO] Nenhuma fatura encontrada.")
                 return

            # Aqui precisamos iterar sobre possíveis linhas de uma tabela, se houver múltiplas faturas
            # O código original buscava apenas o primeiro link XML/DANFE solto. 
            # Vou assumir que pode haver uma tabela.
            
            # Tenta achar linhas de tabela (tr)
            rows = soup.find_all('tr')
            found_docs = False
            
            # Se não tiver tabela explícita, tenta estratégia original (pegar o primeiro que aparecer)
            if not rows or len(rows) < 2:
                # Estratégia original melhorada
                xml_tag = soup.find('a', href=re.compile(r'xml', re.I))
                danfe_tag = soup.find('a', href=re.compile(r'pdf|danfe', re.I))
                
                if xml_tag or danfe_tag:
                    found_docs = True
                    # Tenta achar numero da fatura próximo
                    # Nem sempre é fácil, vamos usar timestamp se falhar
                    invoice_id = datetime.now().strftime("%Y%m%d")
                    
                    if xml_tag:
                        self.baixar(xml_tag['href'], "XML", invoice_id)
                    if danfe_tag:
                        self.baixar(danfe_tag['href'], "DANFE", invoice_id)
            else:
                # Se tiver tabela, tenta processar cada linha (exceto header)
                for row in rows:
                    if not row.find('td'): continue # Header
                    
                    cols = row.find_all('td')
                    # Tenta achar links nela
                    links = row.find_all('a')
                    xml_link = next((l['href'] for l in links if 'xml' in l['href'].lower() or 'xml' in l.text.lower()), None)
                    pdf_link = next((l['href'] for l in links if 'pdf' in l['href'].lower() or 'pdf' in l.text.lower()), None)
                    
                    if xml_link or pdf_link:
                        found_docs = True
                        # Tenta pegar algum ID da linha
                        unique_id = cols[0].get_text(strip=True) if cols else datetime.now().strftime("%Y%m%d_%H%M%S")
                        unique_id = sanitize_name(unique_id)
                        
                        if xml_link: self.baixar(xml_link, "XML", unique_id)
                        if pdf_link: self.baixar(pdf_link, "DANFE", unique_id)

            if not found_docs:
                print(f"    [AVISO] Nenhum link de XML/PDF encontrado na página.")

        except Exception as e:
            print(f"    [ERRO] Exceção durante processamento: {e}")

    def baixar(self, href, tipo, doc_id):
        ext = ".xml" if tipo == "XML" else ".pdf"
        filename = f"{tipo}_{self.ons_code}_{datetime.now().strftime('%Y%m%d')}_{doc_id}{ext}"
        target = os.path.join(self.output_path, filename)
        self.baixar_arquivo(href, target, tipo)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="WebETTM Robot")
    parser.add_argument("--empresa", type=str, help="Filtro de Empresa")
    parser.add_argument("--agente", type=str, help="Filtro de Agente")
    parser.add_argument("--user", type=str)
    parser.add_argument("--password", type=str)
    parser.add_argument("--output_dir", help="Pasta de destino dos downloads")
    
    args = parser.parse_args()
    full_config = carregar_empresas()
    targets = {}

    if args.empresa:
        if args.empresa in full_config:
            targets = full_config[args.empresa]
    else:
        # Default: AETE (ou todas?) Vamos focar em AETE como padrão seguro
        targets = full_config.get("AETE", {})

    if args.agente:
        if args.agente in targets:
             targets = {args.agente: targets[args.agente]}
        else:
             # Busca global
             for grp, items in full_config.items():
                 if args.agente in items:
                     targets = {args.agente: items[args.agente]}
                     break
    
    print(f"Iniciando WebETTM para {len(targets)} alvos...")
    for code, name in targets.items():
        bot = ETTMRobot("ETTM", code, name, output_dir=args.output_dir)
        bot.processar()
