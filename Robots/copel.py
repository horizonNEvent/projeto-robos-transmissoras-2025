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
            resp = self.session.post(self.url_boletos, data=data, headers=headers, timeout=(10, 60))
            
            if resp.status_code == 200:
                self.extrair_view_state(resp.text)
                if "<?xml" in resp.text:
                    match = re.search(r'id="formMsg:resultado"><!\[CDATA\[(.*?)]]>', resp.text, re.DOTALL)
                    if match: return match.group(1)
                return resp.text
            return ""
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
            resp = self.session.post(self.url_boletos, files=payload, headers=headers, timeout=60)
            
            if resp.status_code == 200 and len(resp.content) > 500:
                if b"<!DOCTYPE html" in resp.content[:100]:
                    self.logger.warning("Download retornou HTML de erro.")
                    return False
                
                os.makedirs(output_dir, exist_ok=True)
                full_path = os.path.join(output_dir, nome_arquivo)
                with open(full_path, 'wb') as f:
                    f.write(resp.content)
                self.logger.info(f"Salvo: {nome_arquivo}")
                return True
                
            self.logger.warning(f"Falha download {nome_arquivo}: Status {resp.status_code}")
            return False
            
        except Exception as e:
            self.logger.error(f"Erro download: {e}")
            return False

    def run(self):
        if not self.login():
            return

        # Lista de ONS para processar
        # Se passado --agente via args, usa ele. Senão, tenta carregar do JSON ou usa lista hardcoded.
        agentes_para_processar = []
        
        if self.args.agente:
            agentes_para_processar.append({"cod": self.args.agente, "nome": "Agente Solicitado"})
        else:
            # Lista padrão do script original ou carregamento do JSON de empresas se existir
            # Para simplificar agora, se não passar agente, vamos assumir que o usuário deve passar.
            # Ou podemos tentar carregar Data/empresas_copel.json se quisermos.
            # Vamos deixar um aviso.
            try:
                 with open(os.path.join(os.path.dirname(__file__), '..', 'Data', 'empresas_copel.json'), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Estrutura esperada: {"Grupo": {"COD": "Nome"}}
                    for grp, items in data.items():
                        if grp != "config":
                            for k, v in items.items():
                                agentes_para_processar.append({"cod": k, "nome": v})
            except:
                self.logger.warning("Não foi possível carregar lista de agentes padrão. Passe --agente ou configure Data/empresas_copel.json")

        if not agentes_para_processar and not self.args.agente:
            self.logger.error("Nenhum agente ONS definido para busca.")
            return

        base_output_dir = self.get_output_path()

        for agente in agentes_para_processar:
            cod_ons = agente["cod"]
            nome_ons = agente["nome"]
            
            self.logger.info(f"Processando agente: {nome_ons} ({cod_ons})")
            
            html = self.buscar_faturas_por_ons(cod_ons)
            if not html: continue
            
            soup = BeautifulSoup(html, 'html.parser')
            rows = soup.find_all('tr', class_='ui-widget-content')
            if not rows: rows = soup.find_all('tr')[1:] # Fallback
            
            if not rows:
                self.logger.info("Nenhuma fatura encontrada.")
                continue

            # Agrupar por Pedido
            faturas_por_pedido = {}
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 10:
                    pedido = cols[1].text.strip()
                    if pedido not in faturas_por_pedido: faturas_por_pedido[pedido] = []
                    faturas_por_pedido[pedido].append(row)
            
            # Processar cada pedido (Pegando o mais recente ou filtrando pela competencia se implementado)
            for pedido, lista_rows in faturas_por_pedido.items():
                # Lógica original: Pega o mais recente
                # Se quisermos usar self.args.competencia, podemos filtrar aqui.
                # Ex: se self.args.competencia == "202511", filtra referencias de nov/2025.
                
                rows_to_process = []
                
                if self.args.competencia:
                    # Filtra pela competencia desejada
                    target_ano = int(self.args.competencia[:4])
                    target_mes = int(self.args.competencia[4:6])
                    
                    for r in lista_rows:
                        ano_r, mes_r = parse_referencia(r.find_all('td')[0].text.strip())
                        if ano_r == target_ano and mes_r == target_mes:
                            rows_to_process.append(r)
                            
                    if not rows_to_process:
                        # Se não achou da competência exata, pula (ou avisa)
                        # self.logger.info(f"Pedido {pedido}: Sem faturas para competência {self.args.competencia}")
                        pass
                else:
                    # Comportamento padrão: Mais recente
                    if lista_rows:
                        ref_mais_recente = max(lista_rows, key=lambda r: parse_referencia(r.find_all('td')[0].text.strip()))
                        texto_ref_recente = ref_mais_recente.find_all('td')[0].text.strip()
                        rows_to_process = [r for r in lista_rows if r.find_all('td')[0].text.strip() == texto_ref_recente]

                if not rows_to_process: continue
                
                # Define pasta de saída: TUST/COPEL/{Agente}/{Pedido}
                # Ou TUST/COPEL/{Agente}/NF_{Numero}
                # Vamos seguir o padrão de pasta por NF e Agente
                
                # No script original ele cria subpasta por Pedido. Podemos manter.
                # Mas para padronizar com os outros, talvez melhor por NF?
                # Vamos manter Pedido por segurança por enquanto ou jogar tudo na pasta do Agente.
                
                current_output = os.path.join(base_output_dir, cod_ons) # Pasta do agente
                
                for row in rows_to_process:
                    cols = row.find_all('td')
                    ref_slug = cols[0].text.strip().replace("/", "-")
                    doc_num = cols[2].text.strip() # Boleto num?
                    nf_num = cols[3].text.strip() # NF num?
                    valor = cols[6].text.strip().replace(".", "").replace(",", ".")
                    
                    # Nome do arquivo
                    # prefixo = f"NF_{nf_num}_ref_{ref_slug}_R${valor}"
                    prefixo = f"PED_{pedido}_NF_{nf_num}_{ref_slug}"
                    prefixo = re.sub(r'[\\/*?:"<>|]', "", prefixo)

                    # Links
                    a_xml = cols[7].find('a')
                    a_danfe = cols[8].find('a')
                    a_boleto = cols[9].find('a')
                    
                    # Cria subpasta para a NF para organizar melhor
                    nf_folder = os.path.join(current_output, f"NF_{nf_num}")
                    
                    if a_xml and a_xml.get('id'):
                        self.baixar_documento(a_xml.get('id'), f"{prefixo}.xml", cod_ons, nf_folder)
                    if a_danfe and a_danfe.get('id'):
                        self.baixar_documento(a_danfe.get('id'), f"{prefixo}_DANFE.pdf", cod_ons, nf_folder)
                    if a_boleto and a_boleto.get('id'):
                        self.baixar_documento(a_boleto.get('id'), f"{prefixo}_BOLETO.pdf", cod_ons, nf_folder)

if __name__ == "__main__":
    robot = CopelRobot()
    robot.run()
