import os
import time
import datetime
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin

try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

# Disable warnings for clean output
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class OnsRobot(BaseRobot):
    def __init__(self):
        super().__init__("ons")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.output_dir = self.get_output_path()

    def get_target_period(self):
        """
        Retorna a competência no formato YYYY-MM.
        Se passada por argumento (ex: 202512), formata para 2025-12.
        Caso contrário, usa o mês atual.
        """
        if self.args.competencia:
            # Assume formato YYYYMM vindo do args
            c = self.args.competencia
            if len(c) == 6:
                return f"{c[:4]}-{c[4:]}"
            return c
        
        # Default: Mês atual
        now = datetime.datetime.now()
        return now.strftime("%Y-%m")

    def login(self, username, password):
        self.logger.info(f"Iniciando login para: {username}")
        
        try:
            # Step 1: Initial Access
            start_url = "https://sintegre.ons.org.br/"
            self.logger.info(f"Acessando {start_url}...")
            response = self.session.get(start_url, allow_redirects=True, verify=False)
            
            if "sso.ons.org.br" not in response.url and "sintegre.ons.org.br" in response.url:
                self.logger.info("Já logado ou redirecionado diretamente.")
                return True

            # Step 2: Parse Login Page
            soup = BeautifulSoup(response.text, 'html.parser')
            form = soup.find('form', id='kc-form-login')
            
            if not form:
                self.logger.error("Formulário de login não encontrado.")
                return False

            action_url = form.get('action')
            if not action_url.startswith('http'):
                action_url = urljoin(response.url, action_url)

            # Prepare Payload
            payload = {
                'username': username,
                'password': password,
                'credentialId': ''
            }
            # Add hidden fields
            for hidden in form.find_all("input", type="hidden"):
                name = hidden.get('name')
                value = hidden.get('value', '')
                if name and name not in payload:
                    payload[name] = value

            # Step 3: Login POST
            self.logger.info("Enviando credenciais...")
            login_response = self.session.post(action_url, data=payload, allow_redirects=True, verify=False)
            
            # Error Check
            if "kc-feedback-text" in login_response.text:
                soup_err = BeautifulSoup(login_response.text, 'html.parser')
                err = soup_err.find('span', class_='kc-feedback-text')
                self.logger.error(f"Erro de Login: {err.text.strip() if err else 'Desconhecido'}")
                return False

            # Step 4: OIDC Form Post
            soup_oidc = BeautifulSoup(login_response.text, 'html.parser')
            oidc_form = soup_oidc.find('form')
            
            if oidc_form:
                oidc_action = oidc_form.get('action')
                oidc_payload = {i.get('name'): i.get('value', '') for i in oidc_form.find_all('input') if i.get('name')}
                
                self.logger.info("Processando token OIDC...")
                final_response = self.session.post(oidc_action, data=oidc_payload, allow_redirects=True, verify=False)
                
                # Handling Redirect Loops
                current_response = final_response
                for _ in range(3):
                    soup_loop = BeautifulSoup(current_response.text, 'html.parser')
                    forms = soup_loop.find_all('form')
                    
                    target_form = None
                    if soup_loop.find('form', id='FormRedirect'):
                        target_form = soup_loop.find('form', id='FormRedirect')
                        self.logger.info("Processando FormRedirect...")
                    elif len(forms) == 1 and "working" in current_response.text.lower():
                        target_form = forms[0]
                        self.logger.info("Aguardando 'Working' state...")
                    
                    if target_form:
                        action = target_form.get('action') or current_response.url
                        payload_loop = {i.get('name'): i.get('value', '') for i in target_form.find_all('input') if i.get('name')}
                        current_response = self.session.post(action, data=payload_loop, allow_redirects=True, verify=False)
                    else:
                        break
            
            self.logger.info("Login finalizado com sucesso.")
            return True

        except Exception as e:
            self.logger.error(f"Exceção durante login: {e}")
            return False

    def get_context_digest(self):
        self.logger.info("Obtendo FormDigest do SharePoint...")
        try:
            context_url = "https://sintegre.ons.org.br/sites/1/18/_api/contextinfo"
            headers_context = {
                "Accept": "application/json;odata=verbose",
                "Content-Type": "application/json;odata=verbose"
            }
            context_resp = self.session.post(context_url, headers=headers_context, verify=False)
            
            if context_resp.status_code == 200:
                data = context_resp.json()
                return data['d']['GetContextWebInformation']['FormDigestValue']
            else:
                self.logger.error(f"Falha ao obter ContextInfo. Status: {context_resp.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"Erro ao obter digest: {e}")
            return None

    def download_product(self, product_title, file_prefix, agents, dest_dir):
        """Busca e baixa itens da API do ONS (Sintegre)."""
        digest = self.get_context_digest()
        if not digest: return

        target_period = self.get_target_period()
        self.logger.info(f"Buscando '{product_title}' para competência: {target_period}")

        # URL e Query convertida do script original
        api_url = "https://sintegre.ons.org.br/sites/1/18/_api/web/lists/GetByTitle('Produtos')/GetItems?$select=Id,Title,Produto,DataProdutos,FileRef,Periodicidade,PublicarEm,File_x0020_Type,FileLeafRef,Modified,UniqueId,File&$expand=File"
        
        query_payload = {
            "query": {
                "__metadata": {"type": "SP.CamlQuery"},
                "ViewXml": f"""
                    <View Scope='RecursiveAll'>
                        <Query>
                              <Where>
                                <And>
                                    <Eq><FieldRef Name='Title'/><Value Type='Text'>{product_title}</Value></Eq>
                                    <And>
                                        <Gt><FieldRef Name='ID'/><Value Type='Counter'>0</Value></Gt>
                                        <Eq><FieldRef Name='Pasta'/><Value Type='Boolean'>0</Value></Eq>
                                    </And>
                                </And>
                              </Where>
                              <OrderBy Override="TRUE">
                                <FieldRef Name='Periodicidade' Ascending='False' />
                                <FieldRef Name='PublicarEm' Ascending='False' />
                                <FieldRef Name='ID' Ascending='True' />
                              </OrderBy>
                        </Query>
                        <RowLimit>100</RowLimit>
                    </View>
                """
            }
        }
        
        headers_api = {
            "Accept": "application/json;odata=verbose",
            "Content-Type": "application/json;odata=verbose",
            "X-RequestDigest": digest
        }

        try:
            api_response = self.session.post(api_url, json=query_payload, headers=headers_api, verify=False)
            if api_response.status_code != 200:
                self.logger.error(f"Erro na API de Produtos ({product_title}): {api_response.status_code}")
                return

            results = api_response.json().get('d', {}).get('results', [])
            self.logger.info(f"Itens encontrados para {product_title}: {len(results)}")

            count = 0
            for item in results:
                file_ref = item.get('FileRef')
                # Periodicidade ou DataProdutos
                date_ref = item.get('Periodicidade') or item.get('DataProdutos') or item.get('Created', '')
                
                # Log de depuração
                file_name = file_ref.split('/')[-1] if file_ref else "Unknown"
                
                # Check period match
                if str(date_ref).startswith(target_period):
                    if file_ref:
                        download_url = f"https://sintegre.ons.org.br{file_ref}"
                        safe_date = str(date_ref)[:10].replace('-', '')
                        file_name_clean = "".join([c for c in file_name if c.isalnum() or c in ('._- ')])
                        
                        local_path = os.path.join(dest_dir, f"{file_prefix}_{safe_date}_{file_name_clean}")
                        
                        if os.path.exists(local_path):
                            self.logger.info(f"Arquivo já existe, pulando: {file_name_clean}")
                            continue

                        self.logger.info(f"Baixando {product_title}: {file_name_clean}")
                        try:
                            f_resp = self.session.get(download_url, stream=True, verify=False)
                            f_resp.raise_for_status()
                            with open(local_path, 'wb') as f:
                                for chunk in f_resp.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            count += 1
                        except Exception as dl_err:
                            self.logger.error(f"Falha no download de {file_name}: {dl_err}")
                else:
                    self.logger.info(f"   -> Ignorado: Periodicidade {date_ref} não bate com {target_period}")
            
            self.logger.info(f"Total baixado para {product_title}: {count}")

        except Exception as e:
            self.logger.error(f"Erro ao consultar/baixar {product_title}: {e}")

    def run(self):
        user = self.args.user
        password = self.args.password
        
        if not user or not password:
            self.logger.error("Usuário ou senha não fornecidos (--user, --password).")
            return

        if self.login(user, password):
            agents = self.get_agents()
            
            # Pasta de destino unificada
            dest_dir = self.output_dir
            if self.args.empresa:
                dest_dir = os.path.join(self.output_dir, self.args.empresa)
            os.makedirs(dest_dir, exist_ok=True)

            # Baixa boletos e notas fiscais na mesma pasta
            self.download_product("Boletos do EUST", "BOLETO", agents, dest_dir)
            self.download_product("Notas Fiscais EUST", "NF", agents, dest_dir)

if __name__ == "__main__":
    robot = OnsRobot()
    robot.run()
