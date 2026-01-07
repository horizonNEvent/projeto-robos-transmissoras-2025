import requests
import json
import os
import re
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# Configurações de Diretórios
import sqlite3

# Configurações de Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'Data')
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(ROOT_DIR, 'sql_app.db')
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\TUST\WebSigetPublic"

def sanitize_name(name):
    if not name: return "DESCONHECIDO"
    clean = re.sub(r'[<>:"/\\|?*]', '_', str(name))
    return " ".join(clean.split()).strip()

def carregar_targets():
    """Carrega lista de transmissoras do Banco de Dados (SQLite)."""
    targets = {}
    try:
        if not os.path.exists(DB_PATH):
            print(f"[AVISO] Banco de dados não encontrado: {DB_PATH}. Usando JSON se existir...")
            json_path = os.path.join(DATA_DIR, "siget_public_targets.json")
            if os.path.exists(json_path):
                import json
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT codigo_ons, nome FROM siget_public_targets WHERE ativo = 1")
        rows = cursor.fetchall()
        
        for row in rows:
            targets[str(row[0])] = row[1]
            
        conn.close()
        print(f"Carregados {len(targets)} alvos do banco de dados na Tabela siget_public_targets.")
    except Exception as e:
        print(f"Erro ao ler banco de dados: {e}")
    return targets

class SigetPublicRobot:
    def __init__(self, ons_code, ons_name, agent_code):
        self.ons_code = ons_code
        self.ons_name = ons_name
        self.agent_code = agent_code
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        }
        
        safe_ons_name = sanitize_name(self.ons_name)
        folder_name = f"EMC_{self.ons_code}_{safe_ons_name}"
        self.output_path = os.path.join(BASE_DOWNLOAD_PATH, folder_name)
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path, exist_ok=True)

    def processar(self, args_competencia=None):
        print(f"\n>>> [SIGET] Transmissora: {self.ons_code} ({self.ons_name}) | Agente: {self.agent_code}")
        # Calcular competência (YYYYMM)
        # Se veio via ARGV, usa. Senão calcula next month.
        competencia = ""
        if args_competencia:
            competencia = args_competencia
        else:
            from datetime import timedelta
            today = datetime.now()
            next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
            competencia = next_month.strftime("%Y%m")
        
        # URL Correta: transmitter/{COD_TRANS}/invoices?agent={COD_AGENTE}&time={COMPETENCIA}&page=1
        url = f"https://sys.sigetplus.com.br/cobranca/transmitter/{self.ons_code}/invoices?agent={self.agent_code}&time={competencia}&page=1"
        
        # Tenta também o mês ATUAL se não achar nada?
        # Vamos tentar primeiro o calculado.
        
        print(f"    - URL: {url}")        
        try:
            res = self.session.get(url, headers=self.headers, timeout=30)
            if res.status_code != 200:
                print(f"    [ERRO] HTTP {res.status_code} - Provavelmente URL inválida ou portal privado.")
                return

            if "Nenhuma fatura encontrada" in res.text:
                 print(f"    [AVISO] Nenhuma fatura encontrada.")
                 return

            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.find_all('tr')
            found_docs = False
            
            # Estratégia Híbrida (Tabela ou Link Solto)
            
            # 1. Tenta achar links soltos (página simples)
            if not rows or len(rows) < 2:
                xml_tag = soup.find('a', href=re.compile(r'xml', re.I))
                danfe_tag = soup.find('a', href=re.compile(r'pdf|danfe', re.I))
                
                if xml_tag or danfe_tag:
                    found_docs = True
                    invoice_id = datetime.now().strftime("%Y%m%d")
                    if xml_tag: self.baixar(xml_tag['href'], "XML", invoice_id)
                    if danfe_tag: self.baixar(danfe_tag['href'], "DANFE", invoice_id)
            
            # 2. Tenta achar tabela (página com histórico)
            else:
                for row in rows:
                    if not row.find('td'): continue
                    
                    cols = row.find_all('td')
                    links = row.find_all('a')
                    
                    # Filtra links de XML e PDF
                    xml_models = ['xml']
                    pdf_models = ['pdf', 'danfe']
                    boleto_models = ['boleto', 'billet', 'download']

                    xml_link = next((l['href'] for l in links if any(m in l['href'].lower() for m in xml_models)), None)
                    # O PDF "DANFE" geralmente tem 'danfe' ou 'pdf'. 
                    # Se tiver 'download', pode ser qualquer coisa, mas vamos priorizar a busca por DANFE explícito primeiro.
                    # Ajuste: Se o link não for XML e não for Boleto, assumimos que é PDF/DANFE
                    
                    pdf_link = next((l['href'] for l in links if any(m in l['href'].lower() for m in pdf_models)), None)
                    boleto_link = next((l['href'] for l in links if any(m in l['href'].lower() for m in boleto_models)), None)

                    if xml_link or pdf_link or boleto_link:
                        found_docs = True
                        # Tenta pegar ID da primeira coluna
                        unique_id = cols[0].get_text(strip=True) if cols else datetime.now().strftime("%Y%m%d_%H%M%S")
                        unique_id = sanitize_name(unique_id)
                        
                        if xml_link: self.baixar(xml_link, "XML", unique_id)
                        if pdf_link: self.baixar(pdf_link, "DANFE", unique_id)
                        if boleto_link: self.baixar(boleto_link, "BOLETO", unique_id)

            if not found_docs:
                print(f"    [AVISO] Nenhum link de download identificado.")

        except Exception as e:
            print(f"    [ERRO] Exceção: {e}")

    def baixar(self, url_suffix, tipo, invoice_id):
        # A URL pode ser relativa ou absoluta
        if not url_suffix.startswith("http"):
             full_url = urljoin("https://sys.sigetplus.com.br", url_suffix)
        else:
             full_url = url_suffix
             
        filename = f"{tipo}_{self.ons_code}_{invoice_id}.{('xml' if tipo == 'XML' else 'pdf')}"
        path = os.path.join(self.output_path, filename)
        
        if os.path.exists(path):
            print(f"    [SKIP] {tipo} já existe ({filename}).")
            return

        try:
            # Se for Boleto e não tiver .pdf no final (provavelmente HTML), usamos PDFKIT se disponível
            if tipo == "BOLETO" and ".pdf" not in full_url.lower():
                try:
                    import pdfkit
                    # Caminho do wkhtmltopdf HARDCODED igual ao siget.py para garantir
                    WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
                    config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
                    
                    res = self.session.get(full_url, headers=self.headers, timeout=30)
                    if res.status_code == 200:
                        pdfkit.from_string(res.text, path, configuration=config)
                        print(f"    [OK] {tipo} salvo (convertido HTML->PDF).")
                        return
                except Exception as e_kit:
                    print(f"    [AVISO] Falha ao usar pdfkit para Boleto: {e_kit}. Tentando download direto...")

            # Download normal (binário)
            r = self.session.get(full_url, headers=self.headers, timeout=30)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    f.write(r.content)
                print(f"    [OK] {tipo} salvo.")
            else:
                print(f"    [ERRO] HTTP {r.status_code} ao baixar {tipo}.")
        except Exception as e:
            print(f"    [ERRO] Exceção download {tipo}: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="WebSigetPublic Robot")
    parser.add_argument("--empresa", type=str, help="Filtro de Empresa (Ignorado, compatibilidade)")
    parser.add_argument("--agente", type=str, help="Filtro de Agente (Código ONS)")
    parser.add_argument("--user", type=str, help="User (Ignorado)")
    parser.add_argument("--competencia", type=str, help="Competência YYYYMM (Opcional)")
    
    args = parser.parse_args()
    targets = carregar_targets()
    
    final_targets = {}
    
    # O argumento --agente define QUEM ESTÁ ACESSANDO (parametro agent=)
    # Ex: python WebSigetPublic.py --agente 3748
    
    agent_code = args.agente
    if not agent_code:
        print(" [AVISO] Nenhum agente informado (--agente). Usando padrão 0000.")
        agent_code = "0000"

    print(f"Iniciando WebSigetPublic para {len(targets)} transmissoras (Agente: {agent_code}, Comp: {args.competencia or 'AUTO'})...")
    
    for trans_code, trans_name in targets.items():
        # Passamos o agent_code para a classe
        bot = SigetPublicRobot(trans_code, trans_name, agent_code)
        bot.processar(args.competencia)
