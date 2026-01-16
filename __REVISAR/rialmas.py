import os
import json
import re
import requests
import pdfkit
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

# Configurações Globais
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\TUST\RIALMA"
HEADERS_COMMON = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
}

# Configuração do PDFKit (wkhtmltopdf)
WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
PDFKIT_CONFIG = None
if os.path.exists(WKHTMLTOPDF_PATH):
    PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
else:
    print(f"[AVISO] wkhtmltopdf não encontrado em {WKHTMLTOPDF_PATH}. Tentando usar do PATH do sistema.")

# --- Funções Utilitárias ---

def carregar_empresas():
    # Caminho igual ao da assu
    arquivo_json = os.path.join(os.path.dirname(__file__), 'Data', 'empresas.json')
    try:
        if not os.path.exists(arquivo_json):
            print(f"Erro: Arquivo {arquivo_json} não encontrado!")
            return {}

        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar empresas: {e}")
        return {}

def sanitizar_nome(nome):
    """Remove caracteres inválidos e normaliza espaços para uso em caminhos Windows."""
    nome_limpo = re.sub(r'[<>:"/\\|?*\n\r]', ' ', nome)
    nome_limpo = re.sub(r'\s+', ' ', nome_limpo).strip()
    return nome_limpo

def baixar_arquivo(url, caminho_destino, headers=HEADERS_COMMON, session=None):
    try:
        if session:
            resp = session.get(url, headers=headers)
        else:
            resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        
        # Garante que o diretório existe
        os.makedirs(os.path.dirname(caminho_destino), exist_ok=True)
        
        with open(caminho_destino, 'wb') as f:
            f.write(resp.content)
        print(f"[DOWNLOAD] Salvo: {caminho_destino}")
    except Exception as e:
        print(f"[ERRO] Falha ao baixar {url}: {e}")

def html_para_pdf(conteudo_html, caminho_destino):
    try:
        # Garante que o diretório existe
        os.makedirs(os.path.dirname(caminho_destino), exist_ok=True)
        
        # Converte string direto para arquivo
        pdfkit.from_string(conteudo_html, caminho_destino, configuration=PDFKIT_CONFIG)
        print(f"[PDFKIT] Convertido e salvo: {caminho_destino}")
    except Exception as e:
        print(f"[ERRO] Falha ao converter HTML para PDF: {e}")

# --- Módulo SigetPlus (Ex-RIALMA) ---

class SigetPlusDownloader:
    BASE_URL = "https://sys.sigetplus.com.br/cobranca/company/27/invoices"
    
    @staticmethod
    def obter_data_param():
        """Calcula o ano e mês atual, decrementando o mês em 1 (lógica original)."""
        data_atual = datetime.now()
        if data_atual.month == 1:
            mes = 12
            ano = data_atual.year - 1
        else:
            mes = data_atual.month - 1
            ano = data_atual.year
        return f"{ano}{mes:02d}"

    def processar(self, agent_code, nome_ons, empresa_nome):
        time_param = self.obter_data_param()
        url = f"{self.BASE_URL}?agent={agent_code}&time={time_param}&page=1"
        
        # Usar sessão para manter cookies (pode ajudar se houver checks de sessão)
        session = requests.Session()
        session.headers.update(HEADERS_COMMON)
        
        print(f"\n[SIGETPLUS] Processando {empresa_nome} - {nome_ons} (Agent: {agent_code})...")
        try:
            response = session.get(url)
            soup = BeautifulSoup(response.text, "html.parser")
            tabela = soup.find("table", {"class": "table-striped"})
            
            if not tabela:
                print(f"[SIGETPLUS] Tabela não encontrada para {sigla}")
                return

            linhas = tabela.find("tbody").find_all("tr")
            for linha in linhas:
                colunas = linha.find_all("td")
                transmissora = sanitizar_nome(colunas[0].get_text(strip=True))
                numero_fatura = sanitizar_nome(colunas[1].get_text(strip=True))
                
                # Diretório de destino unificado: Root / Empresa / ONS / Transmissora
                transmissora_dir = os.path.join(BASE_DOWNLOAD_PATH, empresa_nome, agent_code, transmissora)
                
                # Links
                boletos_links = [a["href"] for a in colunas[3].find_all("a")]
                nfe_links = [a["href"] for a in colunas[6].find_all("a")]

                # Processar XMLs e DANFEs (NFE)
                xml_finais, danfe_finais = [], []
                for link in nfe_links:
                    self._extrair_links_finais(link, xml_finais, danfe_finais, session)

                # Download Boletos (HTML -> PDF)
                for idx, boleto_url in enumerate(boletos_links, 1):
                    nome = f"boleto_{numero_fatura}_{idx}.pdf"
                    caminho = os.path.join(transmissora_dir, nome)
                    try:
                        # Baixa o HTML do boleto com a MESMA sessão
                        resp = session.get(boleto_url)
                        html_para_pdf(resp.text, caminho)
                    except Exception as e:
                        print(f"[ERRO] Falha ao baixar boleto {boleto_url}: {e}")

                # Download XMLs
                for xml_url in xml_finais:
                    nome = os.path.basename(xml_url)
                    caminho = os.path.join(transmissora_dir, nome)
                    baixar_arquivo(xml_url, caminho, session=session)

                # Download DANFEs
                for danfe_url in danfe_finais:
                    nome = os.path.basename(danfe_url)
                    caminho = os.path.join(transmissora_dir, nome)
                    baixar_arquivo(danfe_url, caminho, session=session)
                    
        except Exception as e:
            print(f"[SIGETPLUS] Erro ao processar {sigla}: {e}")

    def _extrair_links_finais(self, link, xml_list, danfe_list, session):
        try:
            if link.endswith('/XML/'):
                r = session.get(link)
                s = BeautifulSoup(r.text, "html.parser")
                for a in s.find_all("a", href=True):
                    if a["href"].endswith(".xml"):
                        xml_list.append(urljoin(link, a["href"]))
            elif link.endswith('/DANFE/'):
                r = session.get(link)
                s = BeautifulSoup(r.text, "html.parser")
                for a in s.find_all("a", href=True):
                    if a["href"].endswith(".pdf"):
                        danfe_list.append(urljoin(link, a["href"]))
            elif link.endswith('.xml'):
                xml_list.append(link)
            elif link.endswith('.pdf'):
                danfe_list.append(link)
        except Exception as e:
            print(f"[SIGETPLUS] Erro ao resolver link final {link}: {e}")

# --- Módulo Alupar (Ex-RIALMA_IV) ---

class AluparDownloader:
    LOGIN_URL = "https://faturas.alupar.com.br:8090/Fatura/Emissao/4"
    BASE_DOMAIN = "https://faturas.alupar.com.br:8090"

    def processar(self, agent_code, nome_ons, empresa_nome):
        print(f"\n[ALUPAR] Tentando conexão para {empresa_nome} - {nome_ons} (ONS: {agent_code})...")
        
        session = requests.Session()
        session.cookies.set('cmplz_banner-status', 'dismissed', domain='stnordeste.com.br')
        
        headers = {
            'User-Agent': HEADERS_COMMON['User-Agent'],
            'Referer': 'https://stnordeste.com.br/',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': self.BASE_DOMAIN,
            'Upgrade-Insecure-Requests': '1',
        }
        
        payload = {
            'Codigo': agent_code,
            'btnEntrar': 'OK',
            '__RequestVerificationToken': ''
        }
        
        try:
            resp = session.post(self.LOGIN_URL, data=payload, headers=headers)
            if resp.status_code != 200:
                print(f"[ALUPAR] Falha no login. Status: {resp.status_code}")
                return
            
            if "erro" in resp.text.lower() or "error" in resp.text.lower():
                return 

            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table')
            if not table:
                print(f"[ALUPAR] Nenhuma tabela encontrada após login para {sigla}.")
                return

            # Pular cabeçalho
            rows = table.find_all('tr')[1:]
            
            # Coletar dados e datas
            faturas = []
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 7: continue # Precisa ter pelo menos até a data
                
                data_emissao_str = cols[6].text.strip() # Index 6 baseado no RIALMA_IV
                try:
                    dt_obj = datetime.strptime(data_emissao_str, "%d/%m/%Y")
                except ValueError:
                    continue
                
                faturas.append({
                    'row': row,
                    'dt': dt_obj
                })
            
            if not faturas:
                print(f"[ALUPAR] Nenhuma fatura com data válida encontrada para {sigla}.")
                return

            # Filtrar pelo mês/ano mais recente
            # Ordena decrescente para pegar o maior year/month
            faturas.sort(key=lambda x: x['dt'], reverse=True)
            mais_recente = faturas[0]['dt']
            
            # Filtra todas que match o mês/ano da mais recente
            faturas_para_processar = [
                f for f in faturas 
                if f['dt'].month == mais_recente.month and f['dt'].year == mais_recente.year
            ]
            
            print(f"[ALUPAR] Filtrando mês {mais_recente.month}/{mais_recente.year}. Encontradas: {len(faturas_para_processar)}")

            for item in faturas_para_processar:
                row = item['row']
                cols = row.find_all('td')
                
                cliente = sanitizar_nome(cols[3].text) if len(cols) > 3 else "Cliente"
                doc_num = sanitizar_nome(cols[5].text) if len(cols) > 5 else "000"
                
                # Diretório: Root / Empresa / ONS / Cliente
                cliente_dir = os.path.join(BASE_DOWNLOAD_PATH, empresa_nome, agent_code, cliente)
                
                # Links com Javascript (onclick)
                links = row.find_all('a', href=True)
                for link in links:
                    onclick = link.get('onclick', '')
                    title = link.get('title', '')
                    
                    target_url = None
                    nome_arquivo = f"doc_{doc_num}.bin"
                    
                    if 'window.open' in onclick:
                        try:
                            # Extrai URL entre aspas simples
                            part = onclick.split("'")[1]
                            if part.startswith('/'):
                                target_url = self.BASE_DOMAIN + part
                        except IndexError:
                            pass
                    
                    if target_url:
                        timestamp = datetime.now().strftime('%Y%m%d')
                        if 'Visualizar NF' in title: # DANFE
                            nome_arquivo = f"NF_{doc_num}_{timestamp}.pdf"
                        elif 'Baixar XML' in title:
                            nome_arquivo = f"XML_{doc_num}_{timestamp}.xml"
                        elif 'Baixar DANFE' in title:
                            nome_arquivo = f"DANFE_{doc_num}_{timestamp}.pdf"
                        else:
                            if '.xml' in target_url.lower():
                                nome_arquivo = f"Extra_{doc_num}_{timestamp}.xml"
                            elif '.pdf' in target_url.lower():
                                nome_arquivo = f"Extra_{doc_num}_{timestamp}.pdf"
                        
                        caminho_final = os.path.join(cliente_dir, nome_arquivo)
                        baixar_arquivo(target_url, caminho_final, headers=HEADERS_COMMON, session=session)

        except Exception as e:
            print(f"[ALUPAR] Erro geral em {sigla}: {e}")


# --- Orquestrador Principal ---

def main():
    print("=== Iniciando Robô Unificado RIALMA ===")
    print(f"Diretório Base: {BASE_DOWNLOAD_PATH}\n")
    
    empresas = carregar_empresas()
    
    siget = SigetPlusDownloader()
    alupar = AluparDownloader()
    
    for empresa_nome, mapping in empresas.items():
        print(f"\n>>> Processando Empresa: {empresa_nome} <<<")
        for cod_ons, nome_ons in mapping.items():
            # Tenta SigetPlus
            siget.processar(cod_ons, nome_ons, empresa_nome)
            
            # Tenta Alupar (Robô IV)
            alupar.processar(cod_ons, nome_ons, empresa_nome)

    print("\n=== Execução Finalizada ===")

if __name__ == "__main__":
    main()