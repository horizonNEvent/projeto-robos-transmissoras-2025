import requests
import json
from datetime import datetime
import os
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

# Configuração de Diretórios
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'Data')
EMPRESAS_JSON_PATH = os.path.join(DATA_DIR, 'empresas.json')
BASE_DOWNLOAD_PATH = r"C:\Users\Bruno\Downloads\TUST\TECP"

# URL base do sistema de faturas (Alupar Portal)
BASE_URL = "https://faturas.alupar.com.br:8090"
# O ID 56 parece ser específico para a TECP
EMISSAO_URL = f"{BASE_URL}/Fatura/Emissao/56"

def carregar_empresas():
    """Carrega os dados das empresas do arquivo JSON padrão"""
    try:
        if not os.path.exists(EMPRESAS_JSON_PATH):
            print(f"Erro: Arquivo {EMPRESAS_JSON_PATH} não encontrado!")
            return {}
        with open(EMPRESAS_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar empresas: {e}")
        return {}

def obter_dados_nota_recente(session, cod_ons, headers):
    """Obtém os dados da nota fiscal mais recente do portal Alupar (TECP)"""
    data = {
        "Codigo": cod_ons,
        "btnEntrar": "Entrar"  # No TECP é "Entrar", no STN era "OK"
    }
    
    try:
        response = session.post(EMISSAO_URL, data=data, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            tabela = soup.find('table', class_=lambda x: x and 'table-bordered' in x and 'table-hover' in x)
            if not tabela:
                # Fallback para qualquer tabela se a classe mudar
                tabela = soup.find('table')
                
            if tabela:
                tbody = tabela.find('tbody')
                if tbody:
                    linhas = tbody.find_all('tr')
                    if linhas:
                        nota_mais_recente = None
                        data_mais_recente = None
                        
                        for linha in linhas:
                            colunas = linha.find_all(['td', 'th'])
                            if len(colunas) >= 8:
                                # Estrutura Alupar/TECP: [0]Checkbox [1]Transmissora [2]CódONS [3]Cliente [4]CNPJ [5]NºDoc [6]DataEmissão [7]Valor [8]Ação
                                data_str = colunas[6].text.strip()
                                try:
                                    data_nota = datetime.strptime(data_str, '%d/%m/%Y')
                                    if data_mais_recente is None or data_nota > data_mais_recente:
                                        data_mais_recente = data_nota
                                        nota_mais_recente = linha
                                except ValueError:
                                    continue
                        
                        if nota_mais_recente:
                            colunas = nota_mais_recente.find_all(['td', 'th'])
                            dados = {
                                'numero_nf': colunas[5].text.strip(),
                                'data_emissao': colunas[6].text.strip(),
                                'transmissora': colunas[1].text.strip(),
                                'links': []
                            }
                            
                            # Extrai links da coluna de ação (Ação é a última coluna, geralmente índice 8 ou -1)
                            acoes = colunas[-1].find_all('a')
                            for acao in acoes:
                                onclick = acao.get('onclick', '')
                                title = acao.get('title', '').upper()
                                
                                # Extrair URL do onclick: window.open('/Fatura/XML/123?idMov=456&idEmpresa=56', ...)
                                match = re.search(r"window\.open\('([^']+)'", onclick)
                                if match:
                                    url_relativa = match.group(1)
                                    url_completa = urljoin(BASE_URL, url_relativa)
                                    dados['links'].append({
                                        'tipo': 'XML' if 'XML' in title else 'DANFE' if ('DANFE' in title or 'NF' in title) else 'OUTRO',
                                        'url': url_completa,
                                        'title': title
                                    })
                            return dados
    except Exception as e:
        print(f"Erro ao buscar notas para ONS {cod_ons}: {e}")
    
    return None

def obter_dados_boleto_recente(session, cod_ons, headers):
    """Obtém os dados do boleto mais recente (mesma estrutura do STN)"""
    # Para TECP o iCodEmp parece ser 56
    url = f"{BASE_URL}/Home/Boletos?iCodEmp=56&iCodOns={cod_ons}"
    try:
        res = session.get(url, headers=headers)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            tabela = soup.find('table', {'class': 'tableGrid'})
            if tabela:
                # Pega a primeira linha de dados
                linha = tabela.find('tr', {'class': 'dif'})
                if linha:
                    link_download = linha.find('a', href=True)
                    if link_download:
                        href = link_download['href']
                        # O link já é a URL de download do Boleto
                        return urljoin(BASE_URL, href)
    except Exception as e:
        print(f"Erro ao buscar boleto para ONS {cod_ons}: {e}")
    return None

def baixar_fatura(empresa_nome, cod_ons, nome_ons):
    print(f"\n>>> Processando {empresa_nome} | ONS {cod_ons} ({nome_ons})")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://tecpenergia.com.br/"
    }

    session = requests.Session()
    
    # Padrão ASSU: TUST / TECP / Empresa / ONS
    base_path = os.path.join(BASE_DOWNLOAD_PATH, empresa_nome, cod_ons)
    os.makedirs(base_path, exist_ok=True)

    # 1. Baixar XML e DANFE
    dados_nota = obter_dados_nota_recente(session, cod_ons, headers)
    if dados_nota:
        print(f"Nota encontrada: {dados_nota['numero_nf']} de {dados_nota['data_emissao']}")
        for link in dados_nota['links']:
            try:
                res = session.get(link['url'], headers=headers)
                if res.status_code == 200:
                    ext = ".xml" if link['tipo'] == "XML" else ".pdf"
                    timestamp = datetime.now().strftime("%Y%m%d")
                    filename = f"{link['tipo']}_{nome_ons}_{dados_nota['numero_nf']}_{timestamp}{ext}"
                    filepath = os.path.join(base_path, filename)
                    with open(filepath, 'wb') as f:
                        f.write(res.content)
                    print(f"    ✓ {link['tipo']} salvo: {filename}")
            except Exception as e:
                print(f"    ❌ Erro ao baixar {link['tipo']}: {e}")
    else:
        print(f"Aviso: Nenhuma nota encontrada para ONS {cod_ons}")

    # 2. Baixar Boleto (Se existir)
    url_boleto = obter_dados_boleto_recente(session, cod_ons, headers)
    if url_boleto:
        try:
            res = session.get(url_boleto, headers=headers)
            if res.status_code == 200:
                timestamp = datetime.now().strftime("%Y%m%d")
                filename = f"BOLETO_{nome_ons}_{timestamp}.pdf"
                filepath = os.path.join(base_path, filename)
                with open(filepath, 'wb') as f:
                    f.write(res.content)
                print(f"    ✓ BOLETO salvo: {filename}")
        except Exception as e:
            print(f"    ❌ Erro ao baixar BOLETO: {e}")

    return True

def processar_todas():
    print("Iniciando Robô TECP (Portal Alupar)")
    empresas_dict = carregar_empresas()
    if not empresas_dict:
        print("Erro: Nenhuma empresa carregada do JSON.")
        return

    for empresa_nome, ons_dict in empresas_dict.items():
        for cod_ons, nome_ons in ons_dict.items():
            try:
                baixar_fatura(empresa_nome, cod_ons, nome_ons)
            except Exception as e:
                print(f"Erro fatal ao processar {empresa_nome} ({cod_ons}): {e}")

if __name__ == "__main__":
    processar_todas()
    print("\nProcesso finalizado!")