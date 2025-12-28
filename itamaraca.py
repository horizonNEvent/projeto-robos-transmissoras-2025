import requests
import json
from bs4 import BeautifulSoup
import os
from pathlib import Path

# Carrega empresas do JSON compartilhado (Data/empresas.json)
def carregar_empresas():
    try:
        # Caminho igual ao da assu
        arquivo_json = os.path.join(os.path.dirname(__file__), 'Data', 'empresas.json')
        if not os.path.exists(arquivo_json):
            print(f"Erro: Arquivo {arquivo_json} não encontrado!")
            return {}

        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar empresas: {e}")
        return {}

def get_transmissora_data(agent_code):
    base_url = 'https://sys.sigetplus.com.br'
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }
    
    endpoint = f'/cobranca/transmitter/1307/invoices'
    params = {'agent': agent_code}

    try:
        response = requests.get(
            f'{base_url}{endpoint}',
            headers=headers,
            params=params
        )
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Erro ao fazer a requisição para o código {agent_code}: {e}")
        return None

def download_xml(xml_url, save_path):
    try:
        response = requests.get(xml_url)
        response.raise_for_status()
        
        os.makedirs(save_path, exist_ok=True)
        
        file_name = xml_url.split('/')[-1]
        # Adiciona timestamp no nome se preferir padrão idêntico ao da assu
        # Mas mantendo o nome original se for o padrão desta transmissora
        full_path = os.path.join(save_path, file_name)
        
        with open(full_path, 'wb') as f:
            f.write(response.content)
            
        print(f"XML baixado com sucesso: {full_path}")
        return True
    except Exception as e:
        print(f"Erro ao baixar o XML: {e}")
        return False

def extract_xml_url(html_content):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        xml_link = soup.find('a', {'data-original-title': 'XML'})
        
        if xml_link and 'href' in xml_link.attrs:
            return xml_link['href']
        else:
            print("Link do XML não encontrado na página")
            return None
    except Exception as e:
        print(f"Erro ao extrair URL do XML: {e}")
        return None

def process_agent(agent_code, nome_ons, empresa_nome, base_path):
    print(f"\nProcessando {empresa_nome} - {nome_ons} (ONS: {agent_code})")
    
    # Cria o caminho da pasta: Raiz / Empresa / CodigoONS (Igual Assu)
    save_path = os.path.join(base_path, empresa_nome, agent_code)
    
    # Obtém os dados da página
    data = get_transmissora_data(agent_code)
    
    if data:
        # Extrai a URL do XML
        xml_url = extract_xml_url(data)
        
        if xml_url:
            # Faz o download do XML
            download_xml(xml_url, save_path)
        else:
            print(f"Não foi possível encontrar o URL do XML para o código {agent_code}")
    else:
        print(f"Não foi possível obter os dados da página para o código {agent_code}")

def main():
    # Diretório base atualizado para o padrão TUST
    base_path = r'C:\Users\Bruno\Downloads\TUST\ITAMARACA'
    
    empresas = carregar_empresas()
    # Processa todos os códigos a partir do empresas.json (Estrutura: {Empresa: {Cod: Nome}})
    for empresa_nome, mapping in empresas.items():
        print(f"\nProcessando empresa: {empresa_nome}")
        for cod_ons, nome_ons in mapping.items():
            process_agent(str(cod_ons), nome_ons, empresa_nome, base_path)

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()