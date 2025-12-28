import requests
import json
import re
import os
from datetime import datetime
import time
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from urllib.parse import unquote, quote

# Silenciar avisos de parser (JSF retorna XML em requisições AJAX)
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

def parse_referencia(ref_str):
    """Converte 'Mês/Ano' em um objeto comparável (ano, mes)"""
    meses = {
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6,
        'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
    }
    try:
        partes = ref_str.lower().split('/')
        if len(partes) == 2:
            mes_nome = partes[0].strip()
            ano = int(partes[1].strip())
            mes = meses.get(mes_nome, 0)
            return (ano, mes)
    except:
        pass
    return (0, 0)

class CopelDownloader:
    def __init__(self, username, password, empresa_mae=None, cod_ons=None, nome_ons=None):
        self.session = requests.Session()
        self.base_url = "https://www.copel.com/dcsweb/"
        self.url_recupera = "https://www.copel.com/dcsweb/recupera"
        self.url_boletos = "https://www.copel.com/dcsweb/paginas/boletos.jsf"
        
        self.username = username
        self.password = password
        self.cod_ons = cod_ons
        self.nome_ons = nome_ons
        self.empresa_mae = empresa_mae
        
        self.view_state = ""
        self.is_logado = False

        # Organização de pastas padrão do projeto
        if empresa_mae and cod_ons:
            self.download_path = os.path.join(r"C:\Users\Bruno\Downloads\TUST\COPEL", empresa_mae, cod_ons)
        else:
            self.download_path = r"C:\Users\Bruno\Downloads\TUST\COPEL\GERAL"

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }
        self.session = requests.Session()
        # Estabilizar conexão com pool e retries
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=3)
        self.session.mount("https://", adapter)
        self.session.headers.update(self.headers)

    def extrair_view_state(self, html):
        if not html: return ""
        
        # Caso 1: HTML Padrão
        soup = BeautifulSoup(html, 'html.parser')
        vs = soup.find('input', {'name': 'javax.faces.ViewState'})
        if vs:
            self.view_state = vs.get('value')
            return self.view_state
        
        # Caso 2: XML Partial Response (AJAX)
        # O ID pode variar: javax.faces.ViewState ou j_id1:javax.faces.ViewState:0
        vs_match = re.search(r'ViewState.*?><!\[CDATA\[(.*?)]]>', html)
        if vs_match:
            self.view_state = vs_match.group(1)
            return self.view_state
            
        return ""

    def login(self):
        try:
            print(f"Iniciando login no portal COPEL para {self.username}...")
            
            # Cabeçalhos sincronizados com o navegador
            nav_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Connection": "keep-alive",
                "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"'
            }

            # 1. Acessar a Home - Pegar URL do SSO
            resp_home = self.session.get(self.base_url, headers=nav_headers, allow_redirects=True)
            
            soup = BeautifulSoup(resp_home.text, 'html.parser')
            form = soup.find('form')
            
            from urllib.parse import urljoin
            if form and form.get('action'):
                url_login_action = urljoin(resp_home.url, form.get('action'))
            else:
                url_login_action = resp_home.url
            
            print(f"Postando login para: {url_login_action[:80]}...")

            # 2. POST de Login no SSO
            login_data = {
                "username": self.username,
                "password": self.password
            }
            
            # Adicionar Referer da página de login
            post_headers = nav_headers.copy()
            post_headers["Referer"] = resp_home.url
            post_headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            time.sleep(2) # Pausa estratégica
            resp_login = self.session.post(url_login_action, data=login_data, headers=post_headers, allow_redirects=True)
            
            if resp_login.status_code != 200:
                print(f"Erro no login: Status {resp_login.status_code}")
                if resp_login.status_code == 400:
                    print(resp_login.text[:500])
                return False

            # 3. Capturar Access Token do Histórico
            urls_para_checar = [resp_login.url] + [r.url for r in resp_login.history]
            access_token = None
            
            for u in urls_para_checar:
                match = re.search(r"access_token=([^&|#\s]+)", u)
                if match:
                    access_token = unquote(match.group(1))
                    break
            
            if not access_token:
                if "invalid_credentials" in resp_login.text.lower() or "inválida" in resp_login.text.lower():
                    print("Erro: Credenciais inválidas.")
                else:
                    print("Falha ao capturar token. Verifique o fluxo do portal.")
                return False
            
            print("Token capturado!")

            # 4. Validar Token no DCSWEB (Fluxo exato do navegador)
            url_transicao = "https://www.copel.com/dcsweb/paginaswa/loginkey.jsf"
            
            recup_headers = {
                "User-Agent": self.headers["User-Agent"],
                "token": quote(access_token),
                "Referer": url_transicao,
                "Origin": "https://www.copel.com",
                "Content-Type": "application/x-www-form-urlencoded",
                "Connection": "keep-alive"
            }
            recup_data = {"token": access_token}
            
            # Oficializar sessão
            self.session.post(self.url_recupera, data=recup_data, headers=recup_headers)

            # 5. Pegar ViewState Final na página de boletos
            boletos_headers = {
                "User-Agent": self.headers["User-Agent"],
                "Referer": url_transicao,
                "Upgrade-Insecure-Requests": "1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Connection": "keep-alive"
            }
            
            resp_boletos = self.session.get(self.url_boletos, headers=boletos_headers)
            print(f"Status Página Boletos: {resp_boletos.status_code}")
            
            if self.extrair_view_state(resp_boletos.text):
                self.is_logado = True
                print("Login COPEL (SSO) realizado com sucesso!")
                return True
            
            # Se falhou, pode ser que o ViewState esteja escondido ou a página não carregou
            if "javax.faces.ViewState" not in resp_boletos.text:
                print("Erro: ViewState não encontrado na página de boletos.")
            
            return False
        except Exception as e:
            print(f"Erro crítico no login COPEL: {e}")
            return False

    def buscar_faturas_por_ons(self):
        """Filtra as faturas pelo código ONS da empresa atual"""
        try:
            # Payload IDÊNTICO ao manual fornecido
            data = {
                "javax.faces.partial.ajax": "true",
                "javax.faces.source": "formMsg:j_idt31",
                "javax.faces.partial.execute": "@all",
                "javax.faces.partial.render": "formMsg:filtro formMsg:resultado",
                "formMsg:j_idt31": "formMsg:j_idt31",
                "formMsg": "formMsg",
                "formMsg:filtroBtn_input": "on",
                "formMsg:cnpj": "",
                "formMsg:cpf": "",
                "formMsg:ons_input": "",
                "formMsg:ons_hinput": self.cod_ons,
                "formMsg:empresas_focus": "",
                "formMsg:ref_focus": "",
                "formMsg:ref_input": "",
                "javax.faces.ViewState": self.view_state
            }
            
            headers = {
                "Accept": "application/xml, text/xml, */*; q=0.01",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Faces-Request": "partial/ajax",
                "Origin": "https://www.copel.com",
                "Referer": self.url_boletos,
                "User-Agent": self.headers["User-Agent"],
                "X-Requested-With": "XMLHttpRequest",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "Connection": "keep-alive",
                "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"'
            }
            
            print(f"    Filtrando ONS {self.cod_ons}... (Aguardando resposta do portal - pode levar 10s)")
            # Timeout generoso: 10s para conectar, 60s para ler (portal é lento)
            resp = self.session.post(self.url_boletos, data=data, headers=headers, timeout=(10, 60))
            
            if resp.status_code == 200:
                print(f"    Resposta recebida ({len(resp.text)} bytes)")
                # Atualizar ViewState
                self.extrair_view_state(resp.text)
                
                if "<?xml" in resp.text:
                    match = re.search(r'id="formMsg:resultado"><!\[CDATA\[(.*?)]]>', resp.text, re.DOTALL)
                    if match:
                        return match.group(1)
                return resp.text
            else:
                print(f"    Erro no filtro: Status {resp.status_code}")
        except Exception as e:
            print(f"    Falha na requisição de filtro: {e}")
        return ""

    def baixar_documento(self, link_id, nome_arquivo):
        """Simula o POST de download (Multipart) conforme manual do usuário"""
        try:
            # Payload EXATO do curl fornecido pelo usuário
            data_fields = {
                "formMsg": "formMsg",
                "formMsg:filtroBtn_input": "on",
                "formMsg:cnpj": "",
                "formMsg:cpf": "",
                "formMsg:ons_input": "",
                "formMsg:ons_hinput": self.cod_ons,
                "formMsg:empresas_focus": "",
                "formMsg:ref_focus": "",
                "formMsg:ref_input": "",
                "javax.faces.ViewState": self.view_state,
                link_id: link_id
            }
            
            payload = {k: (None, str(v)) for k, v in data_fields.items()}
            
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9",
                "Origin": "https://www.copel.com",
                "Referer": self.url_boletos,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Connection": "keep-alive"
            }
            
            time.sleep(1.5) # Delay entre downloads para estabilidade
            resp = self.session.post(self.url_boletos, files=payload, headers=headers, timeout=60)
            
            content_type = resp.headers.get('content-type', '').lower()
            
            # Se status 200, vamos tentar processar o arquivo independente do content-type restrito
            if resp.status_code == 200 and len(resp.content) > 500:
                # Verificar se não é uma página de erro (HTML) disfarçada
                if b"<!DOCTYPE html" in resp.content[:100] or b"<html" in resp.content[:100]:
                    print(f"        [AVISO] Portal retornou HTML em vez de arquivo.")
                    return False
                
                os.makedirs(self.download_path, exist_ok=True)
                path = os.path.join(self.download_path, nome_arquivo)
                with open(path, 'wb') as f:
                    f.write(resp.content)
                print(f"        [OK] {nome_arquivo}")
                return True
            else:
                print(f"        [FALHA] Resposta inválida: {content_type} (Tam: {len(resp.content)})")
            return False
        except Exception as e:
            print(f"        [ERRO] Download interrompido: {e}")
            return False

def carregar_config():
    with open(os.path.join(os.path.dirname(__file__), 'Data/empresas.json'), 'r', encoding='utf-8') as f:
        empresas = json.load(f)
    
    # Carregar credenciais específicas da COPEL
    try:
        with open(os.path.join(os.path.dirname(__file__), 'Data/empresas_copel.json'), 'r', encoding='utf-8') as f:
            credenciais = json.load(f)
    except:
        credenciais = {"config": {"usuario": "", "senha": ""}}
        
    return empresas, credenciais

def main():
    empresas_config, copel_cred = carregar_config()
    
    USER_COPEL = copel_cred["config"]["usuario"]
    PASS_COPEL = copel_cred["config"]["senha"]

    if not USER_COPEL or not PASS_COPEL:
        print("Erro: Credenciais da COPEL não encontradas no arquivo JSON.")
        return

    # Criar um downloader mestre para o login inicial
    master = CopelDownloader(USER_COPEL, PASS_COPEL)
    
    if master.login():
        for empresa_mae, cod_ons_dict in empresas_config.items():
            print(f"\n--- Grupo: {empresa_mae} ---")
            for cod_ons, nome_ons in cod_ons_dict.items():
                print(f"Processando {nome_ons} ({cod_ons})...")
                
                # Reaproveitar a sessão logada do mestre para a empresa específica
                worker = CopelDownloader(USER_COPEL, PASS_COPEL, empresa_mae, cod_ons, nome_ons)
                worker.session = master.session
                worker.view_state = master.view_state
                
                html_resultado = worker.buscar_faturas_por_ons()
                if not html_resultado: continue
                
                soup = BeautifulSoup(html_resultado, 'html.parser')
                # A tabela do PrimeFaces costuma ter essa classe nas linhas de dados
                rows = soup.find_all('tr', class_='ui-widget-content')
                
                if not rows:
                    rows = soup.find_all('tr')[1:]

                if not rows:
                    print("    Nenhuma fatura encontrada para este ONS.")
                    continue

                # 1. Agrupar faturas por "Número do pedido" e encontrar a referência mais recente
                faturas_por_pedido = {}
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 10:
                        ref_texto = cols[0].text.strip()
                        pedido = cols[1].text.strip()
                        
                        if pedido not in faturas_por_pedido:
                            faturas_por_pedido[pedido] = []
                        faturas_por_pedido[pedido].append(row)

                print(f"    Filtrando as referências mais recentes para os {len(faturas_por_pedido)} pedidos encontrados...")

                # 2. Processar cada pedido baixando apenas a referência mais atual
                for pedido, lista_rows in faturas_por_pedido.items():
                    # Encontrar a data mais recente entre as faturas deste pedido
                    ref_mais_recente = max(lista_rows, key=lambda r: parse_referencia(r.find_all('td')[0].text.strip()))
                    texto_ref_recente = ref_mais_recente.find_all('td')[0].text.strip()
                    
                    # Filtrar apenas as linhas que batem com essa referência recente
                    linhas_para_baixar = [r for r in lista_rows if r.find_all('td')[0].text.strip() == texto_ref_recente]
                    
                    print(f"    Pedido {pedido}: Baixando referência {texto_ref_recente} ({len(linhas_para_baixar)} itens)")
                    
                    # Atualizar caminho de download para incluir a subpasta do pedido
                    original_path = worker.download_path
                    worker.download_path = os.path.join(original_path, pedido)
                    
                    for row in linhas_para_baixar:
                        cols = row.find_all('td')
                        # Índices corrigidos conforme snippet: 0:Ref, 1:Pedido, 2:Boleto, 3:NF, 5:Venc, 6:Valor
                        ref_slug = cols[0].text.strip().replace("/", "-")
                        doc_num = cols[2].text.strip()
                        venc = cols[5].text.strip().replace("/", "-")
                        valor = cols[6].text.strip().replace(".", "").replace(",", ".")
                        
                        prefixo = f"{ref_slug}_Pedido_{pedido}_Boleto_{doc_num}_Venc_{venc}_R${valor}"
                        prefixo = re.sub(r'[\\/*?:"<>|]', "_", prefixo)
                        
                        # Extrair IDs dos links de download
                        a_xml = cols[7].find('a')
                        a_danfe = cols[8].find('a')
                        a_boleto = cols[9].find('a')
                        
                        if a_xml and a_xml.get('id'):
                            worker.baixar_documento(a_xml.get('id'), f"XML_{prefixo}.xml")
                        
                        if a_danfe and a_danfe.get('id'):
                            worker.baixar_documento(a_danfe.get('id'), f"DANFE_{prefixo}.pdf")
                            
                        if a_boleto and a_boleto.get('id'):
                            worker.baixar_documento(a_boleto.get('id'), f"BOLETO_{prefixo}.pdf")
                    
                    # Restaurar caminho base para o próximo loop (opcional mas boa prática)
                    worker.download_path = original_path

    else:
        print("Finalizado: Não foi possível autenticar no portal da COPEL.")

if __name__ == "__main__":
    main()
