import requests
import json
from datetime import datetime
import os
from bs4 import BeautifulSoup
import re
import argparse

BASE_URL = "https://faturamentoassu.cesbe.com.br"
from utils_paths import get_base_download_path, ensure_dir
BASE_DIR_DEFAULT = get_base_download_path("ASSU")

# Carregar o arquivo empresas.json
with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Data/empresas.json'), 'r', encoding='utf-8') as f:
    EMPRESAS = json.load(f)

def obter_dados_nota_recente(session, base_url, cod_ons, headers):
    """Obtém os dados da nota fiscal mais recente"""
    response = session.get(f"{base_url}/Home/Notas?iCodEmp=18&iCodOns={cod_ons}", headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # Procura a tabela com classe 'tableGrid'
        tabela = soup.find('table', {'class': 'tableGrid'})
        if tabela:
            # Pega todas as linhas da tabela exceto o cabeçalho
            linhas = tabela.find_all('tr', {'class': 'dif'})
            if linhas:
                # A última linha é a nota mais recente
                ultima_linha = linhas[-1]
                dados = {}
                # Extrai os dados da linha
                colunas = ultima_linha.find_all('td')
                dados['numero_nf'] = colunas[0].text.strip()
                dados['data_emissao'] = colunas[1].text.strip()
                dados['valor'] = colunas[2].text.strip()
                dados['chave_nfe'] = colunas[3].text.strip()
                
                # Extrai a chave NFe do link do XML
                link_xml = ultima_linha.find('a', href=True, string='Xml')
                if link_xml:
                    href = link_xml['href']
                    chave = href.split('sChvDoe=')[1]
                    dados['chave_nfe'] = chave
                
                print(f"Dados da nota mais recente para ONS {cod_ons}:")
                print(json.dumps(dados, indent=2))
                return dados
    return None

def obter_dados_boleto_recente(session, base_url, cod_ons, headers):
    """Obtém os dados do boleto mais recente"""
    response = session.get(f"{base_url}/Home/Boletos?iCodEmp=18&iCodOns={cod_ons}", headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        tabela = soup.find('table', {'class': 'tableGrid'})
        if tabela:
            linhas = tabela.find_all('tr', {'class': 'dif'})
            if linhas:
                # A última linha é o boleto mais recente
                linha = linhas[-1]
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

def baixar_titulo(empresa_nome, cod_ons, nome_ons, output_dir=None):
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
    
    # Login com os dados corretos
    response = session.post(
        f"{base_url}/",
        data={
            "CodOns": cod_ons,
            "CodEmp": "18"
        },
        headers=headers
    )
    
    if response.status_code == 200:
        # Criar estrutura de pastas dentro de ASSU
        base_path = os.path.join(output_dir or BASE_DIR_DEFAULT, empresa_nome, cod_ons)
        ensure_dir(base_path)

        # Obtém dados da nota fiscal mais recente
        dados_nota = obter_dados_nota_recente(session, base_url, cod_ons, headers)
        if dados_nota:
            # Download do XML
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
                params=params_xml,  # Usa os mesmos parâmetros do XML
                headers={**headers, "referer": f"{base_url}/Home/Notas?iCodEmp=18&iCodOns={cod_ons}"}
            )
            
            if response_danfe.status_code == 200:
                danfe_path = os.path.join(base_path, f"DANFE_{nome_ons}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
                with open(danfe_path, 'wb') as f:
                    f.write(response_danfe.content)
                print(f"DANFE baixada com sucesso: {danfe_path}")

        # Download do boleto
        dados_boleto = obter_dados_boleto_recente(session, base_url, cod_ons, headers)
        if dados_boleto:
            response_download = session.get(
                f"{base_url}/Home/DownloadBoleto",
                params=dados_boleto,
                headers=headers
            )
            
            if response_download.status_code == 200:
                boleto_path = os.path.join(base_path, f"Boleto_{nome_ons}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
                with open(boleto_path, 'wb') as f:
                    f.write(response_download.content)
                print(f"Boleto baixado com sucesso: {boleto_path}")
                return True

    else:
        print(f"Erro na autenticação para ONS {cod_ons}: {response.status_code}")
    return False

def processar_todas_empresas():
    parser = argparse.ArgumentParser()
    parser.add_argument("--empresa", help="Nome da empresa para filtrar")
    parser.add_argument("--agente", help="Código ONS do agente para filtrar")
    parser.add_argument("--output_dir", help="Pasta de destino dos downloads")
    args = parser.parse_args()

    for empresa_nome, cod_ons_dict in EMPRESAS.items():
        if args.empresa and args.empresa.strip().upper() != empresa_nome.strip().upper():
            continue
            
        print(f"\nProcessando empresa: {empresa_nome}")
        
        filtro_agentes = []
        if args.agente:
            filtro_agentes = [a.strip() for a in str(args.agente).split(',')]

        for cod_ons, nome_ons in cod_ons_dict.items():
            if filtro_agentes and str(cod_ons).strip() not in filtro_agentes:
                continue
                
            try:
                baixar_titulo(empresa_nome, cod_ons, nome_ons, output_dir=args.output_dir)
            except Exception as e:
                print(f"Erro ao processar {empresa_nome} - ONS {cod_ons} - {nome_ons}: {str(e)}")
            print("-" * 50)

if __name__ == "__main__":
    processar_todas_empresas()
