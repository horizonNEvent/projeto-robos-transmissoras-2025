import requests
import json
from datetime import datetime
import os
from bs4 import BeautifulSoup
import re

def carregar_empresas():
    """Carrega os dados das empresas do arquivo JSON"""
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

# Carrega os dados das empresas do arquivo JSON
EMPRESAS = carregar_empresas()

# URL base do sistema de faturas
BASE_URL = "https://faturas.alupar.com.br:8090"

def obter_dados_nota_recente_novo_sistema(session, base_url, cod_ons, headers):
    """Obtém os dados da nota fiscal mais recente do novo sistema"""
    # Baseado no HAR: faz POST para /Fatura/Emissao/1 com Codigo=4313&btnEntrar=OK
    url = f"{base_url}/Fatura/Emissao/1"
    data = {
        "Codigo": cod_ons,
        "btnEntrar": "OK"
    }
    
    response = session.post(url, data=data, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # Procura por tabela com classes específicas do novo sistema
        tabela = soup.find('table', class_=lambda x: x and 'table-bordered' in x and 'table-hover' in x)
        if tabela:
            tbody = tabela.find('tbody')
            if tbody:
                linhas = tbody.find_all('tr')
                if linhas:
                    nota_mais_recente = None
                    data_mais_recente = None
                    
                    for linha in linhas:
                        colunas = linha.find_all('td')
                        if len(colunas) >= 9:  # Ajustado para 9 colunas
                            # Nova estrutura: [0]Checkbox [1]Empresa [2]CódONS [3]Cliente [4]CNPJ [5]NºDoc [6]DataEmissão [7]Valor [8]Ação
                            data_str = colunas[6].text.strip()  # Data de Emissão
                            try:
                                data_nota = datetime.strptime(data_str, '%d/%m/%Y')
                                if data_mais_recente is None or data_nota > data_mais_recente:
                                    data_mais_recente = data_nota
                                    nota_mais_recente = linha
                            except ValueError:
                                continue
                    
                    if nota_mais_recente:
                        colunas = nota_mais_recente.find_all('td')
                        dados = {
                            'numero_nf': colunas[5].text.strip(),  # Nº Documento
                            'data_emissao': colunas[6].text.strip(),  # Data de Emissão
                            'valor': colunas[7].text.strip(),  # Valor Total
                            'chave_nfe': '',
                            'id_fatura': '',
                            'id_mov': '',
                        }
                        
                        # Extrai IDs dos links de ação na coluna 8
                        acoes = colunas[8].find_all('a')
                        for acao in acoes:
                            onclick = acao.get('onclick', '')
                            if 'XML' in onclick:
                                # Procura por padrão /Fatura/XML/1511717?idMov=8443&idEmpresa=1
                                match = re.search(r'/Fatura/XML/(\d+)\?idMov=(\d+)', onclick)
                                if match:
                                    dados['id_fatura'] = match.group(1)
                                    dados['id_mov'] = match.group(2)
                        
                        print(f"Dados da nota mais recente para ONS {cod_ons} (Data: {dados['data_emissao']}):")
                        print(json.dumps(dados, indent=2))
                        return dados
    
    return None

def obter_dados_nota_recente(session, base_url, cod_ons, headers):
    """Obtém os dados da nota fiscal mais recente por data"""
    
    # Primeiro tenta o novo sistema
    dados_novo = obter_dados_nota_recente_novo_sistema(session, base_url, cod_ons, headers)
    if dados_novo:
        return dados_novo
    
    # Se não funcionar, usa o sistema antigo
    response = session.get(f"{base_url}/Home/Notas?iCodEmp=18&iCodOns={cod_ons}", headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        tabela = soup.find('table', {'class': 'tableGrid'})
        if tabela:
            linhas = tabela.find_all('tr')
            linhas_validas = []
            
            for linha in linhas:
                colunas = linha.find_all('td')
                if len(colunas) >= 4:
                    primeiro_campo = colunas[0].text.strip()
                    if primeiro_campo and primeiro_campo.lower() not in ['nº', 'numero', 'número', 'n°']:
                        linhas_validas.append(linha)
            
            if linhas_validas:
                nota_mais_recente = None
                data_mais_recente = None
                
                for linha in linhas_validas:
                    colunas = linha.find_all('td')
                    if len(colunas) >= 4:
                        data_str = colunas[1].text.strip()
                        try:
                            data_nota = datetime.strptime(data_str, '%d/%m/%Y')
                            if data_mais_recente is None or data_nota > data_mais_recente:
                                data_mais_recente = data_nota
                                nota_mais_recente = linha
                        except ValueError:
                            continue
                
                if nota_mais_recente:
                    colunas = nota_mais_recente.find_all('td')
                    dados = {
                        'numero_nf': colunas[0].text.strip(),
                        'data_emissao': colunas[1].text.strip(),
                        'valor': colunas[2].text.strip(),
                        'chave_nfe': colunas[3].text.strip()
                    }
                    
                    # Extrai a chave NFe do link do XML
                    link_xml = nota_mais_recente.find('a', href=True, string='Xml')
                    if link_xml:
                        href = link_xml['href']
                        chave = href.split('sChvDoe=')[1]
                        dados['chave_nfe'] = chave
                    
                    print(f"Dados da nota mais recente para ONS {cod_ons} (Data: {dados['data_emissao']}):")
                    print(json.dumps(dados, indent=2))
                    return dados
    
    return None

def obter_dados_boleto_recente(session, base_url, cod_ons, headers):
    """Obtém os dados do boleto mais recente por data"""
    response = session.get(f"{base_url}/Home/Boletos?iCodEmp=18&iCodOns={cod_ons}", headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        tabela = soup.find('table', {'class': 'tableGrid'})
        if tabela:
            # Pega todas as linhas da tabela
            linhas = tabela.find_all('tr', {'class': 'dif'})
            if linhas:
                # Para boletos, geralmente a primeira linha já é a mais recente
                # Mas vamos pegar a primeira linha disponível
                linha = linhas[0]
                # Encontra o link de download do boleto
                link_download = linha.find('a', href=True)
                if link_download:
                    # Extrai os parâmetros do link
                    href = link_download['href']
                    params = {}
                    for param in href.split('?')[1].split('&'):
                        if '=' in param:
                            key, value = param.split('=')
                            params[key] = value.replace('%20', ' ').replace('%2F', '/').replace('%3A', ':')
                    
                    # Extrai apenas os parâmetros necessários
                    dados_boleto = {
                        "CodEmp": params.get('CodEmp', '18'),
                        "CodFil": params.get('CodFil', '2'),
                        "NumTit": params.get('NumTit', ''),
                        "CodTpt": params.get('CodTpt', 'DP'),
                        "VlrAbe": params.get('VlrAbe', ''),
                        "CodPor": params.get('CodPor', '341'),
                        "CodCrt": params.get('CodCrt', 'SI'),
                        "TitBan": params.get('TitBan', ''),
                        "CgcCpf": params.get('CgcCpf', '33485728000100'),
                        "CodPar": params.get('CodPar', '1'),
                        "CodOns": cod_ons,
                        "CodSel": params.get('CodSel', '1'),
                        "RecUnn": params.get('RecUnn', ''),
                        "ModBlo": params.get('ModBlo', 'FRCR223.BLO'),
                        "NomBan": params.get('NomBan', 'BANCO ITAU S.A.')
                    }
                    
                    print(f"Dados do boleto mais recente para ONS {cod_ons}:")
                    print(json.dumps(dados_boleto, indent=2))
                    return dados_boleto
    return None

def baixar_titulo(empresa_nome, cod_ons, nome_ons):
    print(f"\nProcessando {empresa_nome} - ONS {cod_ons} - {nome_ons}")

    base_url = BASE_URL
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "max-age=0",
        "content-type": "application/x-www-form-urlencoded",
        "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    }

    session = requests.Session()
    
    # Criar estrutura de pastas dentro de STN
    base_path = os.path.join(r"C:\Users\Bruno\Downloads\TUST\STN", empresa_nome, cod_ons)
    os.makedirs(base_path, exist_ok=True)

    # Obtém dados da nota fiscal mais recente (já faz a autenticação internamente)
    dados_nota = obter_dados_nota_recente(session, base_url, cod_ons, headers)
    if dados_nota:
        # Verifica se é do novo sistema ou antigo
        if 'id_fatura' in dados_nota and dados_nota['id_fatura']:
            # Novo sistema
            xml_url = f"{base_url}/Fatura/XML/{dados_nota['id_fatura']}?idMov={dados_nota['id_mov']}&idEmpresa=1"
            danfe_url = f"{base_url}/Fatura/DownloadDANFE?idFatura={dados_nota['id_fatura']}"
            
            # Download do XML
            response_xml = session.get(xml_url, headers=headers)
            if response_xml.status_code == 200:
                xml_path = os.path.join(base_path, f"NFe_{nome_ons}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml")
                with open(xml_path, 'wb') as f:
                    f.write(response_xml.content)
                print(f"XML baixado com sucesso: {xml_path}")

            # Download da DANFE
            response_danfe = session.get(danfe_url, headers=headers)
            if response_danfe.status_code == 200:
                danfe_path = os.path.join(base_path, f"DANFE_{nome_ons}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
                with open(danfe_path, 'wb') as f:
                    f.write(response_danfe.content)
                print(f"DANFE baixada com sucesso: {danfe_path}")
        
        else:
            # Sistema antigo
            params_xml = {
                "sCodEmp": "18",
                "sChvDoe": dados_nota['chave_nfe']
            }
            
            response_xml = session.get(
                f"{base_url}/Home/WsDownloadXml",
                params=params_xml,
                headers={**headers, "referer": f"{base_url}/Home/Notas?iCodEmp=18&iCodOns={cod_ons}"}
            )
            
            if response_xml.status_code == 200:
                xml_path = os.path.join(base_path, f"NFe_{nome_ons}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml")
                with open(xml_path, 'wb') as f:
                    f.write(response_xml.content)
                print(f"XML baixado com sucesso: {xml_path}")

            # Download da DANFE
            response_danfe = session.get(
                f"{base_url}/Home/WsDownloadDanfe",
                params=params_xml,
                headers={**headers, "referer": f"{base_url}/Home/Notas?iCodEmp=18&iCodOns={cod_ons}"}
            )
            
            if response_danfe.status_code == 200:
                danfe_path = os.path.join(base_path, f"DANFE_{nome_ons}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
                with open(danfe_path, 'wb') as f:
                    f.write(response_danfe.content)
                print(f"DANFE baixada com sucesso: {danfe_path}")
        
        return True
    else:
        print(f"Não foi possível obter dados da nota fiscal para ONS {cod_ons}")
        return False

def processar_todas_empresas():
    for empresa_nome, ons_dict in EMPRESAS.items():
        print(f"\nProcessando empresa: {empresa_nome}")
        for cod_ons, nome_ons in ons_dict.items():
            try:
                baixar_titulo(empresa_nome, cod_ons, nome_ons)
            except Exception as e:
                print(f"Erro ao processar {empresa_nome} - ONS {cod_ons} - {nome_ons}: {str(e)}")
            print("-" * 50)

if __name__ == "__main__":
    processar_todas_empresas()