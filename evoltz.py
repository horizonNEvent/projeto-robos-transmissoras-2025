import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime
import time
import pdfkit

# Configuração do PDFKit (wkhtmltopdf) - Seguindo padrão RIALMA/TAESA
WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
PDFKIT_CONFIG = None
if os.path.exists(WKHTMLTOPDF_PATH):
    PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

# Carregar o arquivo empresas.json
with open(os.path.join(os.path.dirname(__file__), 'Data/empresas.json'), 'r', encoding='utf-8') as f:
    EMPRESAS = json.load(f)

class NBTE:
    def __init__(self, empresa_mae=None, cod_ons=None, nome_ons=None):
        self.session = requests.Session()
        self.base_url = "https://www2.nbte.com.br"
        self.empresa_mae = empresa_mae
        self.cod_ons = cod_ons
        self.nome_ons = nome_ons
        
        # Organização do caminho igual ao da ASSU
        if empresa_mae and cod_ons:
            self.download_path = os.path.join(r"C:\Users\Bruno\Downloads\TUST\EVOLTZ", empresa_mae, cod_ons)
        else:
            self.download_path = r"C:\Users\Bruno\Downloads\TUST\EVOLTZ\GERAL"
            
        self.headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'cache-control': 'max-age=0',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www2.nbte.com.br',
            'referer': 'https://www2.nbte.com.br/',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
        }

    def login(self):
        try:
            response = self.session.get(self.base_url, headers=self.headers)
            response.raise_for_status()
            
            data = {
                'cod-ons-login': self.cod_ons,
                'AcaoClick': 'doLogin',
                'idChave': ''
            }

            response = self.session.post(self.base_url, data=data, headers=self.headers)
            response.raise_for_status()
            
            if "EVOLTZ" in response.text and "ERPCom" in response.text:
                print(f"Login realizado com sucesso para {self.nome_ons} ({self.cod_ons})!")
                return True
            else:
                print(f"Falha no login para {self.nome_ons} ({self.cod_ons}). Resposta inesperada.")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"Erro ao fazer login para {self.cod_ons}: {e}")
            return False

    def get_faturas(self):
        try:
            response = self.session.get(self.base_url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # INSIGHT C#: Capturar a competência (filtro_mesano)
            filtro_mesano = ""
            select_mes = soup.find('select', {'name': 'filtro_mesano'})
            if select_mes:
                option = select_mes.find('option')
                if option:
                    filtro_mesano = option.get('value', '')
            
            table = soup.find('table', {'id': '_dataTable'})
            if not table:
                print("Tabela de faturas não encontrada")
                return [], ""
            
            faturas = []
            rows = table.find_all('tr')[1:] # Pula cabeçalho
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 6:
                    transmissora = cols[0].text.strip()
                    num_fatura = cols[1].find('a').text.strip() if cols[1].find('a') else ''
                    
                    # Links para documentos
                    links = {
                        'fatura': cols[1].find('a')['href'] if cols[1].find('a') else None,
                        'boleto': cols[3].find('a')['href'] if cols[3].find('a') else None,
                        'danfe': cols[4].find('a')['href'] if cols[4].find('a') else None,
                        'xml_download': cols[5].find_all('a')[1]['href'] if len(cols[5].find_all('a')) > 1 else None
                    }
                    
                    faturas.append({
                        'transmissora': transmissora,
                        'numero_fatura': num_fatura,
                        'links': links
                    })
            
            return faturas, filtro_mesano
            
        except Exception as e:
            print(f"Erro ao buscar faturas: {e}")
            return [], ""

    def download_documento(self, acao, id_doc, filtro_mesano, nome_arquivo, transmissora_nome):
        try:
            # INSIGHT C#: Payload exato conforme o script .NET
            data = {
                'filtro_mesano': filtro_mesano,
                'AcaoClick': acao,
                'idChave': id_doc
            }
            
            # Limpar o nome da transmissora para usar como pasta
            subpasta = re.sub(r'[^\w\s-]', '', transmissora_nome).strip().replace(' ', '_')
            pasta_final = os.path.join(self.download_path, subpasta)
            os.makedirs(pasta_final, exist_ok=True)
            
            headers = self.headers.copy()
            headers['Referer'] = self.base_url
            
            time.sleep(1.5)
            
            response = self.session.post(self.base_url, data=data, headers=headers)
            
            if response.status_code == 200:
                # FORÇAR ENCODING: O portal usa ISO-8859-1 (Latin-1)
                # Precisamos decodificar corretamente antes de converter
                response.encoding = 'iso-8859-1'
                
                content_type = response.headers.get('content-type', '').lower()
                caminho_arquivo = os.path.join(pasta_final, nome_arquivo)
                
                # Se for PDF ou XML real
                if 'application/pdf' in content_type or 'xml' in content_type:
                    with open(caminho_arquivo, 'wb') as f:
                        f.write(response.content)
                    print(f"Sucesso [{subpasta}]: {nome_arquivo}")
                    return True
                
                # Se for HTML (Boleto/Fatura) -> Converter para PDF
                elif 'html' in content_type:
                    if PDFKIT_CONFIG:
                        if caminho_arquivo.lower().endswith('.html'):
                            caminho_arquivo = caminho_arquivo[:-5] + '.pdf'
                        
                        # MELHORIA: Injetar <base> e CORRIGIR ENCODING para UTF-8
                        # Trocamos a tag meta para o pdfkit não se perder
                        html_corrigido = response.text.replace('<head>', f'<head><base href="{self.base_url}/">')
                        html_corrigido = html_corrigido.replace('iso-8859-1', 'utf-8').replace('ISO-8859-1', 'utf-8')
                        
                        options = {
                            'encoding': "UTF-8",
                            'load-error-handling': 'ignore',
                            'print-media-type': '',
                            'page-size': 'A4',
                            'margin-top': '0mm',
                            'margin-right': '0mm',
                            'margin-bottom': '0mm',
                            'margin-left': '0mm',
                            'zoom': '0.95',
                            'no-outline': '',
                            'quiet': ''
                        }
                        
                        try:
                            pdfkit.from_string(html_corrigido, caminho_arquivo, configuration=PDFKIT_CONFIG, options=options)
                            print(f"Sucesso (HTML->PDF) [{subpasta}]: {os.path.basename(caminho_arquivo)}")
                        except Exception as e:
                            caminho_html = caminho_arquivo.replace('.pdf', '.html')
                            with open(caminho_html, 'w', encoding='utf-8') as f:
                                f.write(html_corrigido)
                            print(f"Aviso: Salvo como HTML devido a erro de conversão [{subpasta}]")
                        return True
                    else:
                        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        print(f"Sucesso (HTML) [{subpasta}]: {nome_arquivo}")
                        return True
                else:
                    print(f"Tipo ignorado para {nome_arquivo}: {content_type}")
                    return False
            else:
                print(f"Erro {response.status_code} em {acao}")
                return False
            
        except Exception as e:
            print(f"Erro no download {nome_arquivo}: {e}")
            return False

def extrair_acao_e_id(link_js):
    """Extrai a ação e o id do link Javascript"""
    if not link_js: return None, None
    # Pega os parâmetros da função callAcaoClick
    match = re.search(r"'(.*?)','(.*?)','(\d+)'", link_js)
    if match:
        return match.group(1), match.group(3)
    return None, None

def processar_empresa(empresa_mae, cod_ons, nome_ons):
    nbte = NBTE(empresa_mae, cod_ons, nome_ons)
    
    if nbte.login():
        faturas, filtro_mesano = nbte.get_faturas()
        
        if faturas:
            print(f"Iniciando downloads para {nome_ons} (Mês: {filtro_mesano})")
            for fatura in faturas:
                n = fatura['numero_fatura']
                t_nome = fatura['transmissora']
                
                # Fatura (Evoltz entrega como HTML)
                if fatura['links']['fatura']:
                    acao, id_doc = extrair_acao_e_id(fatura['links']['fatura'])
                    if acao and id_doc:
                        nbte.download_documento(acao, id_doc, filtro_mesano, f"fatura_{n}.html", t_nome)
                
                # Boleto (Evoltz entrega como HTML)
                if fatura['links']['boleto']:
                    acao, id_doc = extrair_acao_e_id(fatura['links']['boleto'])
                    if acao and id_doc:
                        nbte.download_documento(acao, id_doc, filtro_mesano, f"boleto_{n}.html", t_nome)
                
                # DANFE (PDF)
                if fatura['links']['danfe']:
                    acao, id_doc = extrair_acao_e_id(fatura['links']['danfe'])
                    if acao and id_doc:
                        nbte.download_documento(acao, id_doc, filtro_mesano, f"danfe_{n}.pdf", t_nome)
                
                # XML
                if fatura['links']['xml_download']:
                    acao, id_doc = extrair_acao_e_id(fatura['links']['xml_download'])
                    # Fallback para o XML que às vezes tem formato diferente
                    if not acao:
                         match = re.search(r"'(.*?)','(.*?)','(\d+)'", fatura['links']['xml_download'])
                         if match: acao, id_doc = match.group(1), match.group(3)
                    
                    if acao and id_doc:
                        nbte.download_documento(acao, id_doc, filtro_mesano, f"xml_{n}.xml", t_nome)
        else:
            print(f"Nenhuma fatura para {nome_ons}.")
    else:
        print(f"Falha no login de {nome_ons}.")

def main():
    for empresa_mae, cod_ons_dict in EMPRESAS.items():
        print(f"\n=== GRUPO: {empresa_mae} ===")
        for cod_ons, nome_ons in cod_ons_dict.items():
            processar_empresa(empresa_mae, cod_ons, nome_ons)

if __name__ == "__main__":
    main()
