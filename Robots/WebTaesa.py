import requests
import json
import os
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup

# Configurações de Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\TUST\WebTaesa"

# Tenta configurar o pdfkit se disponível
try:
    import pdfkit
    WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH) if os.path.exists(WKHTMLTOPDF_PATH) else None
except:
    PDFKIT_CONFIG = None

class WebTaesaRobot:
    def __init__(self, agent_code, agent_name, empresa="AETE"):
        self.agent_code = agent_code
        self.agent_name = agent_name
        self.empresa = empresa
        self.session = requests.Session()
        self.base_url = "https://sys.sigetplus.com.br/cobranca"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        # Estrutura de Pastas: Downloads/TUST/WebTaesa/{EMPRESA}/{AGENT}/{TRANSMISSORA}/
        self.base_output_path = os.path.join(BASE_DOWNLOAD_PATH, self.empresa, str(self.agent_code))
        os.makedirs(self.base_output_path, exist_ok=True)

    def sanitize_filename(self, name):
        if not name: return "DESCONHECIDO"
        # Remove caracteres inválidos para Windows e substitui por _
        clean = re.sub(r'[<>:"/\\|?*]', '', str(name))
        # Remove quebras de linha, tabs e espaços excessivos
        clean = " ".join(clean.split())
        # Trunca para evitar caminhos muito longos
        return clean[:150].strip()

    def processar(self, competencia_arg=None):
        """
        Lógica principal de processamento.
        competencia_arg: YYYYMM (opcional). Se None, usa mês anterior (padrão Taesa).
        """
        print(f"\n>>> [TAESA] Processando Agente: {self.agent_code} ({self.agent_name})")

        # Define Competência
        if competencia_arg:
            competencia = competencia_arg
        else:
            # Padrão original: Mês Anterior
            now = datetime.now()
            m, y = (now.month - 1, now.year) if now.month > 1 else (12, now.year - 1)
            competencia = f"{y}{m:02d}"
        
        print(f"    Competência alvo: {competencia}")
        
        page = 1
        total_baixados = 0
        
        while True:
            # URL fixa para Taesa (Company 30)
            url = f"{self.base_url}/company/30/invoices"
            params = {
                "agent": self.agent_code, 
                "time": competencia, 
                "page": page, 
                "_": int(datetime.now().timestamp() * 1000)
            }
            
            try:
                print(f"    - Acessando página {page}...")
                res = self.session.get(url, params=params, headers=self.headers, timeout=30)
                if res.status_code != 200:
                    print(f"    [ERRO] HTTP {res.status_code} na página {page}.")
                    break
                
                # Extrair Faturas
                soup = BeautifulSoup(res.text, 'html.parser')
                rows = soup.select('table tbody tr')
                
                if not rows:
                    if page == 1: print("    [AVISO] Nenhuma fatura encontrada.")
                    break
                
                faturas_encontradas = False
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) < 8: continue
                    faturas_encontradas = True
                    
                    transmissora_nome = self.sanitize_filename(cols[0].get_text(strip=True))
                    num_fatura = self.sanitize_filename(cols[1].get_text(strip=True))
                    
                    # Links
                    links = {}
                    # Link Fatura (Detalhes)
                    if cols[1].find('a'): 
                        links['fatura'] = cols[1].find('a')['href']
                    
                    # Boleto (Coluna 5 - index 4)
                    if cols[4].find('a'): 
                        links['boleto'] = cols[4].find('a')['href']
                    
                    # Botões de Ação (Coluna 8 - index 7)
                    xml_btn = cols[7].find('a', class_='btn-primary')
                    if xml_btn: links['xml'] = xml_btn['href']
                    
                    danfe_btn = cols[7].find('a', class_='btn-info')
                    if danfe_btn: links['danfe'] = danfe_btn['href']

                    if links:
                        # Criar pasta da Transmissora
                        transmissora_path = os.path.join(self.base_output_path, transmissora_nome)
                        os.makedirs(transmissora_path, exist_ok=True)
                        
                        base_filename = f"{num_fatura}_{competencia}"
                        
                        if 'xml' in links: 
                            self.baixar(links['xml'], f"{base_filename}_XML", transmissora_path, 'xml')
                        
                        if 'danfe' in links: 
                            self.baixar(links['danfe'], f"{base_filename}_DANFE", transmissora_path, 'pdf')
                            
                        if 'boleto' in links: 
                            self.baixar(links['boleto'], f"{base_filename}_BOLETO", transmissora_path, 'pdf', is_boleto=True)
                        
                        total_baixados += 1
                
                # Paginação
                next_btn = soup.select('ul.pagination li a[rel="next"]')
                if not next_btn:
                    break
                
                page += 1
                time.sleep(1)

            except Exception as e:
                print(f"    [ERRO] Exceção processamento: {e}")
                break
        
        print(f"    Total processado para este agente: {total_baixados}")

    def baixar(self, url_suffix, name_base, dest_folder, ext_padrao, is_boleto=False):
        if not url_suffix: return

        # Construir URL Completa
        if not url_suffix.startswith("http"):
            full_url = f"{self.base_url}/{url_suffix}" if not url_suffix.startswith("/") else f"https://sys.sigetplus.com.br{url_suffix}"
            # Ajuste feio mas necessário pois as vezes vem relativo ao root ou relativo ao path
            if "../" in url_suffix: full_url = f"https://sys.sigetplus.com.br/cobranca/{url_suffix}"
        else:
            full_url = url_suffix

        # Determinar extensão final
        final_ext = f".{ext_padrao}"
        # Se for Boleto HTML, tentaremos baixar como .html e converter
        if is_boleto and ".pdf" not in full_url.lower() and ".html" not in full_url.lower():
             # URL sem extensão explicita, assumir HTML se for boleto
             pass

        filename = f"{name_base}{final_ext}"
        filepath = os.path.join(dest_folder, filename)

        if os.path.exists(filepath):
            # print(f"        [SKIP] Arquivo existe: {filename}")
            return

        try:
            r = self.session.get(full_url, headers=self.headers, stream=True, timeout=60)
            if r.status_code == 200:
                # Checar Content-Type para confirmar extensão
                ctype = r.headers.get('Content-Type', '').lower()
                real_ext = final_ext
                
                saving_as_html_for_conversion = False
                
                if is_boleto and 'html' in ctype and PDFKIT_CONFIG:
                    real_ext = ".html"
                    saving_as_html_for_conversion = True
                
                temp_path = filepath.replace(final_ext, real_ext)
                
                with open(temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                if saving_as_html_for_conversion:
                    try:
                        pdf_path = filepath # O path original era .pdf
                        pdfkit.from_file(temp_path, pdf_path, configuration=PDFKIT_CONFIG)
                        os.remove(temp_path)
                        print(f"        [OK] {name_base} (HTML->PDF)")
                    except Exception as pk_err:
                        print(f"        [AVISO] Erro converteção PDF: {pk_err}. Mantendo HTML.")
                else:
                    print(f"        [OK] {name_base}")
            else:
                print(f"        [ERRO] Baixar {name_base}: Status {r.status_code}")
        except Exception as e:
            print(f"        [ERRO] Baixar {name_base}: {e}")

if __name__ == "__main__":
    # Teste isolado
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--empresa", default="AETE")
    parser.add_argument("--agente", default="3748") # Exemplo
    parser.add_argument("--competencia", default="")
    
    args = parser.parse_args()
    bot = WebTaesaRobot(args.agente, "TESTE", args.empresa)
    bot.processar(args.competencia)
