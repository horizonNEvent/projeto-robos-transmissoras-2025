import requests
import json
import re
import os
import time
import warnings
from urllib.parse import unquote, quote
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from datetime import datetime

# Import BaseRobot
try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

# Silenciar avisos de parser
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

class CopelRobot(BaseRobot):
    """
    Robô para Portal COPEL (HTTP Requests/JSF).
    """

    def __init__(self):
        super().__init__("copel")
        self.session = requests.Session()
        self.base_url = "https://www.copel.com/dcsweb/"
        self.url_recupera = "https://www.copel.com/dcsweb/recupera"
        self.url_boletos = "https://www.copel.com/dcsweb/paginas/boletos.jsf"
        
        # Estado
        self.view_state = ""
        self.is_logado = False
        
        # Headers Base
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }
        
        # Pool e Retries
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=3)
        self.session.mount("https://", adapter)
        self.session.headers.update(self.headers)

    def extrair_view_state(self, html):
        if not html: return ""
        soup = BeautifulSoup(html, 'html.parser')
        vs = soup.find('input', {'name': 'javax.faces.ViewState'})
        if vs:
            self.view_state = vs.get('value')
            return self.view_state
        
        vs_match = re.search(r'ViewState.*?><!\[CDATA\[(.*?)]]>', html)
        if vs_match:
            self.view_state = vs_match.group(1)
            return self.view_state
        return ""

    def login(self):
        username = self.args.user
        password = self.args.password
        
        if not username or not password:
            self.logger.error("Usuário e Senha são obrigatórios para COPEL.")
            return False

        try:
            self.logger.info(f"Iniciando login no portal COPEL para {username}...")
            
            nav_headers = self.headers.copy()
            nav_headers.update({
                "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"'
            })

            # 1. Home
            resp_home = self.session.get(self.base_url, headers=nav_headers, allow_redirects=True)
            soup = BeautifulSoup(resp_home.text, 'html.parser')
            form = soup.find('form')
            
            from urllib.parse import urljoin
            if form and form.get('action'):
                url_login_action = urljoin(resp_home.url, form.get('action'))
            else:
                url_login_action = resp_home.url
            
            # 2. Login POST
            login_data = {"username": username, "password": password}
            post_headers = nav_headers.copy()
            post_headers["Referer"] = resp_home.url
            post_headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            time.sleep(2)
            resp_login = self.session.post(url_login_action, data=login_data, headers=post_headers, allow_redirects=True)
            
            if resp_login.status_code != 200:
                self.logger.error(f"Erro login status: {resp_login.status_code}")
                return False

            # 3. Token
            urls_para_checar = [resp_login.url] + [r.url for r in resp_login.history]
            access_token = None
            for u in urls_para_checar:
                match = re.search(r"access_token=([^&|#\s]+)", u)
                if match:
                    access_token = unquote(match.group(1))
                    break
            
            if not access_token:
                self.logger.error("Token de acesso não encontrado. Credenciais inválidas?")
                return False
            
            # 4. Validar Token (loginkey.jsf)
            url_transicao = "https://www.copel.com/dcsweb/paginaswa/loginkey.jsf"
            recup_headers = {
                "User-Agent": self.headers["User-Agent"],
                "token": quote(access_token),
                "Referer": url_transicao,
                "Origin": "https://www.copel.com",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            self.session.post(self.url_recupera, data={"token": access_token}, headers=recup_headers)

            # 5. Boletos Page
            resp_boletos = self.session.get(self.url_boletos)
            if self.extrair_view_state(resp_boletos.text):
                self.is_logado = True
                self.logger.info("Login COPEL realizado com sucesso!")
                return True
            
            self.logger.error("Falha ao obter ViewState pós-login.")
            return False

        except Exception as e:
            self.logger.error(f"Exceção no Login: {e}")
            return False

    def buscar_faturas_por_ons(self, cod_ons):
        try:
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
                "formMsg:ons_hinput": cod_ons,
                "formMsg:empresas_focus": "",
                "formMsg:ref_focus": "",
                "formMsg:ref_input": "",
                "javax.faces.ViewState": self.view_state
            }
            
            headers = {
                "Faces-Request": "partial/ajax",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": self.url_boletos,
                "Origin": "https://www.copel.com"
            }
            
            self.logger.info(f"Filtrando ONS {cod_ons}...")
            # Aumentado timeout para evitar RemoteDisconnected prematuro
            resp = self.session.post(self.url_boletos, data=data, headers=headers, timeout=(15, 90))
            
            if resp.status_code == 200:
                self.extrair_view_state(resp.text)
                if "<?xml" in resp.text:
                    match = re.search(r'id="formMsg:resultado"><!\[CDATA\[(.*?)]]>', resp.text, re.DOTALL)
                    if match: return match.group(1)
                return resp.text
            elif resp.status_code == 302 or "login" in resp.url.lower():
                self.logger.warning("Sessão expirada detectada.")
                return "SESSAO_EXPIRADA"
            return ""
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            self.logger.error(f"Erro de conexão filtro ONS: {e}")
            return "ERRO_CONEXAO"
        except Exception as e:
            self.logger.error(f"Erro filtro ONS: {e}")
            return ""

    def baixar_documento(self, link_id, nome_arquivo, cod_ons, output_dir):
        try:
            data_fields = {
                "formMsg": "formMsg",
                "formMsg:filtroBtn_input": "on",
                "formMsg:ons_hinput": cod_ons,
                "javax.faces.ViewState": self.view_state,
                link_id: link_id
            }
            payload = {k: (None, str(v)) for k, v in data_fields.items()}
            
            headers = {
                "Referer": self.url_boletos,
                "Origin": "https://www.copel.com"
            }
            
            time.sleep(1.0)
            resp = self.session.post(self.url_boletos, files=payload, headers=headers, timeout=90)
            
            if resp.status_code == 200 and len(resp.content) > 500:
                if b"<!DOCTYPE html" in resp.content[:100]:
                    self.logger.warning(f"Download retornou HTML (provável erro): {nome_arquivo}")
                    return False
                
                os.makedirs(output_dir, exist_ok=True)
                full_path = os.path.join(output_dir, nome_arquivo)
                with open(full_path, 'wb') as f:
                    f.write(resp.content)
                self.logger.info(f"Salvo: {nome_arquivo}")
                return True
            elif resp.status_code == 302:
                self.logger.warning("Redirecionamento durante download (sessão expirada?)")
                return "RELOGIN"
                
            self.logger.warning(f"Falha download {nome_arquivo}: Status {resp.status_code}")
            return False
            
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            self.logger.error(f"Erro de conexão download: {e}")
            return "RELOGIN"
        except Exception as e:
            self.logger.error(f"Erro download: {e}")
            return False

    def run(self):
        if not self.login():
            return

        agentes_para_processar = []
        if self.args.agente:
            for ag in [a.strip() for a in str(self.args.agente).split(',') if a.strip()]:
                agentes_para_processar.append({"cod": ag, "nome": f"Agente {ag}"})
        else:
            transmissoras_fixas = [
                {"cod": "1008", "nome": "COPEL"},
                {"cod": "1155", "nome": "COPEL (F. DO CHOPIM-S. OSORIO)"},
                {"cod": "1203", "nome": "COPEL (LT ARARAQUARA 2-TAUBATÉ)"},
                {"cod": "1176", "nome": "COPEL (LT BATEIAS-CTBA NORTE)"},
                {"cod": "1219", "nome": "COPEL (LT CTBA LESTE-BLUMENAU)"},
                {"cod": "1091", "nome": "COPEL (LT FOZ - CASCAVEL OESTE)"},
                {"cod": "1140", "nome": "COPEL (SE CERQUILHO III)"},
                {"cod": "1193", "nome": "COPEL (LT ASSIS - LONDRINA C2)"},
                {"cod": "1168", "nome": "COPEL (LT ASSIS-P. PAULISTA II)"},
                {"cod": "1024", "nome": "COPEL (LT BATEIAS-JAGUARIAÍVA)"},
                {"cod": "1063", "nome": "COPEL (LT BATEIAS-PILARZINHO)"},
                {"cod": "1187", "nome": "COPEL (LT FOZ DO CHOPIM-REALEZA)"},
                {"cod": "1144", "nome": "COSTA OESTE"},
                {"cod": "1158", "nome": "MARUMBI"},
                {"cod": "1043", "nome": "UIRAPURU"},
                {"cod": "1218", "nome": "MSGT"}
            ]
            agentes_para_processar.extend(transmissoras_fixas)
            self.logger.info(f"Usando lista fixa de {len(transmissoras_fixas)} transmissoras.")

        if not agentes_para_processar:
            self.logger.error("Nenhum agente ONS definido para busca.")
            return

        base_output_dir = self.get_output_path()

        for agente in agentes_para_processar:
            cod_ons = agente["cod"]
            nome_ons = agente["nome"]
            
            self.logger.info(f"Processando agente: {nome_ons} ({cod_ons})")
            
            # Tentar filtrar faturas com re-login se necessário
            tentativas_relogin = 0
            while tentativas_relogin < 2:
                html = self.buscar_faturas_por_ons(cod_ons)
                
                if html in ["SESSAO_EXPIRADA", "ERRO_CONEXAO"]:
                    self.logger.info("Tentando re-login automático...")
                    time.sleep(5)
                    if self.login():
                        tentativas_relogin += 1
                        continue
                    else:
                        break
                break

            if not html or html in ["SESSAO_EXPIRADA", "ERRO_CONEXAO"]:
                self.logger.warning(f"Não foi possível processar agente {cod_ons} após tentativa de re-login.")
                continue
            
            soup = BeautifulSoup(html, 'html.parser')
            rows = soup.find_all('tr', class_='ui-widget-content')
            if not rows: rows = soup.find_all('tr')[1:]
            
            if not rows:
                self.logger.info("Nenhuma fatura encontrada.")
                continue

            faturas_por_pedido = {}
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 10:
                    pedido = cols[1].text.strip()
                    if pedido not in faturas_por_pedido: faturas_por_pedido[pedido] = []
                    faturas_por_pedido[pedido].append(row)
            
            for pedido, lista_rows in faturas_por_pedido.items():
                rows_to_process = []
                if self.args.competencia:
                    target_ano = int(self.args.competencia[:4])
                    target_mes = int(self.args.competencia[4:6])
                    for r in lista_rows:
                        ano_r, mes_r = parse_referencia(r.find_all('td')[0].text.strip())
                        if ano_r == target_ano and mes_r == target_mes:
                            rows_to_process.append(r)
                else:
                    if lista_rows:
                        ref_mais_recente = max(lista_rows, key=lambda r: parse_referencia(r.find_all('td')[0].text.strip()))
                        texto_ref_recente = ref_mais_recente.find_all('td')[0].text.strip()
                        rows_to_process = [r for r in lista_rows if r.find_all('td')[0].text.strip() == texto_ref_recente]

                if not rows_to_process: continue
                
                current_output = os.path.join(base_output_dir, cod_ons)
                
                for row in rows_to_process:
                    cols = row.find_all('td')
                    ref_slug = cols[0].text.strip().replace("/", "-")
                    nf_num = cols[3].text.strip()
                    
                    prefixo = f"PED_{pedido}_NF_{nf_num}_{ref_slug}"
                    prefixo = re.sub(r'[\\/*?:"<>|]', "", prefixo)

                    links = [
                        (cols[7].find('a'), f"{prefixo}.xml"),
                        (cols[8].find('a'), f"{prefixo}_DANFE.pdf"),
                        (cols[9].find('a'), f"{prefixo}_BOLETO.pdf")
                    ]
                    
                    nf_folder = os.path.join(current_output, f"NF_{nf_num}")
                    
                    for link_tag, fname in links:
                        if link_tag and link_tag.get('id'):
                            res = self.baixar_documento(link_tag.get('id'), fname, cod_ons, nf_folder)
                            if res == "RELOGIN":
                                self.logger.info("Erro no download, tentando re-login e repetindo...")
                                if self.login():
                                    self.baixar_documento(link_tag.get('id'), fname, cod_ons, nf_folder)

if __name__ == "__main__":
    robot = CopelRobot()
    robot.run()
