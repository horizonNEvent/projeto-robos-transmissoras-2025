import os
import json
import logging
import requests
from bs4 import BeautifulSoup
import zipfile
import tempfile
import shutil
import re
from datetime import datetime, timedelta
import sys
import urllib3

# Adicionar o diretório pai ao caminho para poder importar outros módulos, se necessário
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# Desabilita avisos de SSL inseguro
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Diretórios e arquivos dentro deste workspace
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(WORKSPACE_ROOT, 'Data')

# Constantes compartilhadas (prioriza Data/ do workspace)
EMPRESAS_JSON = os.path.abspath(os.path.join(DATA_DIR, 'empresas.json'))
EMPRESAS_IE_JSON_CANDIDATES = [
    os.path.abspath(os.path.join(DATA_DIR, 'empresas_ie.json')),
    r"D:\\Tust_robos\\Empresas\\empresas_ie.json",
]


def get_periodo_padrao():
    """
    Retorna o período padrão no formato 'AAAA|MM', sempre o mês anterior ao mês atual.
    """
    hoje = datetime.now()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_mes = primeiro_dia_mes_atual - timedelta(days=1)
    return f"{ultimo_mes.year}|{str(ultimo_mes.month).zfill(2)}"


# Mock para SharePointHandler (SharePoint desativado neste projeto)
def configurar_sharepoint_para_transmissora_mock(transmissora=None):
    return {}, {}


class SharePointHandlerMock:
    def __init__(self, **kwargs):
        pass

    def autenticar(self, username, password):
        return False

    def criar_pasta(self, caminho_pasta):
        return False

    def upload_arquivo(self, conteudo, nome_arquivo, caminho_pasta):
        return False

    def listar_arquivos(self, caminho_pasta):
        return []


# Força SharePoint indisponível (salvamento local apenas)
SHAREPOINT_DISPONIVEL = False
SharePointHandler = SharePointHandlerMock
configurar_sharepoint_para_transmissora = configurar_sharepoint_para_transmissora_mock


# Funções utilitárias
def carregar_empresas():
    """
    Carrega as informações das empresas do arquivo JSON (Data/empresas.json)

    Retorna:
    - dict: Dicionário com as empresas organizadas por seção (RE/AE/DE)-> lista de {codigo, nome}
    - None: Se houver erro ao carregar o arquivo
    """
    try:
        if not os.path.exists(EMPRESAS_JSON):
            logging.error(f"Erro: Arquivo {EMPRESAS_JSON} não encontrado!")
            return None

        with open(EMPRESAS_JSON, 'r', encoding='utf-8') as f:
            dados = json.load(f)

            empresas_formatadas = {}
            for empresa, codigos in dados.items():
                empresas_formatadas[empresa] = []

                # Se for um dicionário
                if isinstance(codigos, dict):
                    for codigo, nome in codigos.items():
                        empresas_formatadas[empresa].append({"codigo": str(codigo), "nome": nome})
                # Se for uma lista
                elif isinstance(codigos, list):
                    for item in codigos:
                        if isinstance(item, dict):
                            for codigo, nome in item.items():
                                empresas_formatadas[empresa].append({"codigo": str(codigo), "nome": nome})
                        else:
                            empresas_formatadas[empresa].append({"codigo": str(item), "nome": str(item)})

            return empresas_formatadas

    except json.JSONDecodeError:
        logging.error("Erro: Arquivo empresas.json está mal formatado!")
        return None
    except Exception as e:
        logging.error(f"Erro ao carregar empresas: {str(e)}")
        return None


def carregar_credenciais(caminho_custom=None):
    """
    Carrega as credenciais das empresas de um arquivo JSON.
    Se caminho_custom for fornecido, usa ele. Caso contrário, tenta as localizações padrão.

    Retorna:
    - list: Lista com as credenciais das empresas
    - None: Se houver erro ao carregar o arquivo
    """
    try:
        caminho = caminho_custom
        if not caminho:
            for c in EMPRESAS_IE_JSON_CANDIDATES:
                if os.path.exists(c):
                    caminho = c
                    break
        
        if not caminho or not os.path.exists(caminho):
            logging.error(f"Erro: Arquivo de credenciais não encontrado.")
            return None

        with open(caminho, 'r', encoding='utf-8') as f:
            credenciais = json.load(f)

        logging.info(f"Credenciais carregadas do arquivo JSON {caminho}")
        return credenciais

    except json.JSONDecodeError:
        logging.error("Erro: Arquivo de credenciais está mal formatado!")
        return None
    except Exception as e:
        logging.error(f"Erro ao carregar credenciais: {str(e)}")
        return None


# Variável global para armazenar a instância do SharePointHandler
sharepoint_handler = None


def configurar_sharepoint(transmissora=None):
    """
    Mantido por compatibilidade — sempre retorna False (SharePoint desabilitado).
    """
    logging.info("SharePoint desabilitado neste projeto. Salvamento local apenas.")
    return False


def enviar_arquivo_para_sharepoint(conteudo, nome_arquivo, tipo_empresa, nome_pasta, nome_ie):
    """
    Placeholder de upload — sempre retorna False (SharePoint desabilitado).
    """
    logging.debug("Upload para SharePoint desabilitado — ignorando upload.")
    return False


class RobotBase:
    """
    Classe base para robôs de processamento de faturas de IEs (Instalações Elétricas).
    Contém a lógica comum para todos os robôs.
    """

    def __init__(self, nome_ie, url_ie, mapeamento_codigos=None, sharepoint_disponivel=False, caminho_credenciais=None):
        """
        Inicializa um novo robô.

        Parâmetros:
        - nome_ie: Nome da IE (ex: IESUL, EVRECY)
        - url_ie: URL base do site da IE (ex: https://faturamento.iesul.com.br)
        - mapeamento_codigos: Dicionário com mapeamento de códigos ONS para pastas base
        - sharepoint_disponivel: Flag indicando se o SharePoint está disponível (ignorado)
        - caminho_credenciais: Caminho opcional para o arquivo JSON de credenciais
        """
        # Configuração da IE
        self.nome_ie = nome_ie
        # Local de salvamento dinâmico (Raiz / downloads / <IE>)
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_dir = os.path.join(root_dir, "downloads", "TUST", nome_ie)
        self.sites = {nome_ie: url_ie}

        # Mapeamentos e configurações
        self.mapeamento_codigos = mapeamento_codigos or {}
        self.credenciais = carregar_credenciais(caminho_credenciais)
        self.sharepoint_disponivel = False  # sempre local

        # Configuração de logging específica para esta IE
        self.logger = logging.getLogger(nome_ie)

        # Criar diretório base se não existir
        os.makedirs(self.base_dir, exist_ok=True)

        self.logger.info(f"Robô {nome_ie} inicializado. Diretório base: {self.base_dir}")

    def adicionar_site(self, nome, url):
        """Adiciona um novo site à lista de sites para processamento"""
        self.sites[nome] = url
        self.logger.info(f"Site {nome} adicionado com sucesso: {url}")

    def login(self, site_nome, usuario, senha):
        """
        Faz login em um site específico

        Parâmetros:
        - site_nome: Nome do site (chave no dicionário self.sites)
        - usuario: Usuário para login
        - senha: Senha para login

        Retorna:
        - Session: Objeto de sessão com login realizado ou None em caso de erro
        """
        site_url = self.sites.get(site_nome)
        if not site_url:
            self.logger.error(f"Site {site_nome} não encontrado na lista de sites.")
            return None

        # URL do site
        url = f"{site_url}/login.asp"

        # Dados do formulário
        dados_login = {
            'usuario': usuario,
            'senha': senha
        }

        # Headers para simular um navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        try:
            # Fazendo a requisição POST
            sessao = requests.Session()
            resposta = sessao.post(url, data=dados_login, headers=headers, verify=False)

            # Verificando se o login foi bem sucedido
            if resposta.status_code == 200:
                self.logger.info(f"Login {site_nome} realizado com sucesso para usuário {usuario}!")
                return sessao
            else:
                self.logger.error(f"Erro no login {site_nome}. Código de status: {resposta.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Ocorreu um erro no login {site_nome}: {str(e)}")
            return None

    def pesquisar_faturas(self, site_nome, sessao, periodo=None):
        """
        Pesquisa faturas em um site específico

        Parâmetros:
        - site_nome: Nome do site (chave no dicionário self.sites)
        - sessao: Objeto de sessão com login realizado
        - periodo: Período a ser pesquisado no formato "AAAA|MM" (se None, usa mês anterior ao atual)

        Retorna:
        - str: HTML da página com os resultados da pesquisa ou None em caso de erro
        """
        if periodo is None:
            periodo = get_periodo_padrao()

        site_url = self.sites.get(site_nome)
        if not site_url:
            self.logger.error(f"Site {site_nome} não encontrado na lista de sites.")
            return None

        # URL da página de rede básica
        url_rb = f"{site_url}/RB.asp"

        # Headers para simular um navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        try:
            # Primeiro acesso à página
            _ = sessao.get(url_rb, headers=headers, verify=False)

            # Dados para o formulário de pesquisa
            dados_pesquisa = {
                'data': periodo
            }

            # Fazendo a requisição POST para pesquisar
            resposta_pesquisa = sessao.post(url_rb, data=dados_pesquisa, headers=headers, verify=False)

            if resposta_pesquisa.status_code == 200:
                self.logger.info(f"Pesquisa {site_nome} realizada com sucesso para o período {periodo}!")
                return resposta_pesquisa.text
            else:
                self.logger.error(f"Erro na pesquisa {site_nome}. Código de status: {resposta_pesquisa.status_code}")
                return None

        except Exception as e:
            self.logger.error(f"Ocorreu um erro na pesquisa {site_nome}: {str(e)}")
            return None

    def identificar_transmissoras(self, html):
        """
        Identifica as transmissoras e seus códigos no HTML da pesquisa

        Parâmetros:
        - html: HTML da página com os resultados da pesquisa

        Retorna:
        - dict: Dicionário com o mapeamento de transmissoras
        """
        soup = BeautifulSoup(html, 'html.parser')
        transmissoras_identificadas = {}

        # Carregar o mapeamento de códigos ONS para pastas
        empresas = carregar_empresas()
        if not empresas:
            self.logger.warning("Não foi possível carregar o mapeamento de empresas. Usando nomes originais.")

        # Encontrar todas as fieldsets (cada uma representa uma transmissora)
        fieldsets = soup.find_all('fieldset')

        for fieldset in fieldsets:
            legend = fieldset.find('legend')
            if legend:
                nome_transmissora = legend.text.strip()

                tabela = fieldset.find('table')
                if not tabela:
                    continue

                linhas = tabela.find_all('tr')
                if len(linhas) <= 1:  # Apenas o cabeçalho
                    continue

                # Extrair informações da primeira linha de dados da tabela
                primeira_linha = None
                for linha in linhas:
                    colunas = linha.find_all('td')
                    if len(colunas) >= 4 and 'Empreendimento/Contrato' not in colunas[0].text:
                        primeira_linha = linha
                        break

                if not primeira_linha:
                    continue

                colunas = primeira_linha.find_all('td')
                empreendimento = colunas[0].text.strip()
                codigo_ons = colunas[1].text.strip() if len(colunas) > 1 else ''

                # Padrão para extrair código do empreendimento
                codigo_empreendimento = None
                match = re.search(r'^(\d+)', empreendimento)
                if match:
                    codigo_empreendimento = match.group(1)

                # Determinar a pasta_base
                pasta_base = None

                if codigo_ons in self.mapeamento_codigos:
                    pasta_base = self.mapeamento_codigos[codigo_ons]
                elif empresas and codigo_ons:
                    for _, codigos in empresas.items():
                        for item in codigos:
                            if isinstance(item, dict) and item.get('codigo') == codigo_ons:
                                pasta_base = item.get('nome')
                                break

                if not pasta_base:
                    pasta_base = re.sub(r'[^\w\s]', '', nome_transmissora).replace(' ', '_')

                transmissoras_identificadas[nome_transmissora] = {
                    'codigo': codigo_empreendimento if codigo_empreendimento else 'desconhecido',
                    'codigo_ons': codigo_ons,
                    'nome': nome_transmissora,
                    'pasta_base': pasta_base,
                }

        if transmissoras_identificadas:
            self.logger.info(f"Identificadas {len(transmissoras_identificadas)} transmissoras.")
        else:
            self.logger.warning("Nenhuma transmissora identificada no HTML!")

        return transmissoras_identificadas

    def extrair_e_mostrar_transmissoras(self, site_nome, html, empresa):
        """
        Extrai e mostra as transmissoras encontradas na página HTML
        """
        soup = BeautifulSoup(html, 'html.parser')
        self.logger.info(f"\n=== Transmissoras Encontradas {site_nome} ===")

        transmissoras = soup.find_all('fieldset')
        total_geral = 0
        faturas_encontradas = False

        for transmissora in transmissoras:
            legend = transmissora.find('legend')
            if legend:
                nome_transmissora = legend.text.strip()
                self.logger.info(f"\n{nome_transmissora}")
                self.logger.info("-" * 50)

                tabela = transmissora.find('table')
                if tabela:
                    linhas = tabela.find_all('tr')[1:-1]

                    total_transmissora = 0
                    for linha in linhas:
                        colunas = linha.find_all('td')
                        if len(colunas) >= 4:
                            empreendimento = colunas[0].text.strip()
                            codigo_ons = colunas[1].text.strip()
                            fatura = colunas[2].text.strip()
                            valor = colunas[3].text.strip()

                            codigo_empreendimento = 'Desconhecido'
                            match = re.search(r'^(\d+)', empreendimento)
                            if match:
                                codigo_empreendimento = match.group(1)

                            if empreendimento and codigo_ons and 'Total' not in empreendimento:
                                faturas_encontradas = True
                                try:
                                    valor_float = float(valor.replace(',', '.'))
                                    total_transmissora += valor_float
                                except Exception:
                                    pass

                    try:
                        linha_total = tabela.find_all('tr')[-1]
                        valor_total_text = linha_total.find_all('td')[3].text.strip()
                        valor_total = float(valor_total_text.replace(',', '.'))
                        self.logger.info(f"\nTotal {nome_transmissora}: R$ {valor_total:.2f}")
                        total_geral += valor_total
                    except Exception:
                        self.logger.info(f"\nTotal {nome_transmissora}: R$ {total_transmissora:.2f}")
                        total_geral += total_transmissora

        self.logger.info("\n" + "=" * 50)
        self.logger.info(f"Valor Total Geral: R$ {total_geral:.2f}")
        self.logger.info("=" * 50)

        return faturas_encontradas

    def download_documentos(self, site_nome, sessao, html, empresa, pasta_base):
        """
        Baixa os documentos de um site específico
        """
        site_url = self.sites.get(site_nome)
        if not site_url:
            self.logger.error(f"Site {site_nome} não encontrado na lista de sites.")
            return

        soup = BeautifulSoup(html, 'html.parser')
        transmissoras = soup.find_all('fieldset')

        for transmissora in transmissoras:
            legend = transmissora.find('legend')
            if not legend:
                continue

            nome_transmissora = legend.text.strip()
            tabela = transmissora.find('table')
            if not tabela:
                continue

            linhas = tabela.find_all('tr')[1:]

            for linha in linhas:
                colunas = linha.find_all('td')
                if len(colunas) >= 5:
                    empreendimento = colunas[0].text.strip()
                    codigo_ons = colunas[1].text.strip()
                    num_fatura = colunas[2].text.strip()

                    if not empreendimento or 'Total' in empreendimento or 'Empreendimento/Contrato' in empreendimento:
                        continue

                    codigo_empreendimento = 'Desconhecido'
                    match = re.search(r'^(\d+)', empreendimento)
                    if match:
                        codigo_empreendimento = match.group(1)

                    nome_pasta_empreendimento = f"EMC_{codigo_empreendimento}"

                    pasta_destino = os.path.join(self.base_dir, empresa, pasta_base, nome_pasta_empreendimento)
                    if not self.sharepoint_disponivel and not os.path.exists(pasta_destino):
                        os.makedirs(pasta_destino, exist_ok=True)
                        self.logger.info(f"Pasta criada: {pasta_destino}")

                    nome_pasta_sharepoint = f"{pasta_base}_{codigo_empreendimento}"

                    with tempfile.TemporaryDirectory() as temp_dir:
                        base_url = f"{site_url}/download.asp"

                        # Fatura (XML)
                        url_fatura = f"{base_url}?mode=admin&arquivo=zip&tipo=xml&num_fatura={num_fatura}"
                        temp_fatura = os.path.join(temp_dir, f"fatura_{num_fatura}")

                        try:
                            response = sessao.get(url_fatura, verify=False)
                            if response.status_code == 200:
                                with open(temp_fatura, 'wb') as f:
                                    f.write(response.content)
                                self.logger.info(f"Fatura {site_nome} {num_fatura} baixada com sucesso!")

                                content_type = response.headers.get('Content-Type', '')
                                if 'zip' in content_type.lower():
                                    extensao = '.zip'
                                elif 'xml' in content_type.lower():
                                    extensao = '.xml'
                                elif 'pdf' in content_type.lower():
                                    extensao = '.pdf'
                                else:
                                    if response.content.startswith(b'PK'):
                                        extensao = '.zip'
                                    elif response.content.startswith(b'%PDF'):
                                        extensao = '.pdf'
                                    elif response.content.startswith(b'<?xml'):
                                        extensao = '.xml'
                                    else:
                                        extensao = '.dat'

                                self.processar_arquivo(
                                    temp_fatura,
                                    response.content,
                                    extensao,
                                    f"fatura_{num_fatura}",
                                    empresa,
                                    nome_pasta_sharepoint,
                                    pasta_destino,
                                )

                                # Boleto (opcional)
                                url_boleto = f"{base_url}?mode=admin&tipo=boleto&arquivo=zip&num_fatura={num_fatura}"
                                temp_boleto = os.path.join(temp_dir, f"boleto_{num_fatura}")

                                response_boleto = sessao.get(url_boleto, verify=False)
                                if response_boleto.status_code == 200 and len(response_boleto.content) > 0:
                                    with open(temp_boleto, 'wb') as f:
                                        f.write(response_boleto.content)

                                    if response_boleto.content.startswith(b'%PDF'):
                                        boleto_ext = '.pdf'
                                    elif response_boleto.content.startswith(b'PK'):
                                        boleto_ext = '.zip'
                                    else:
                                        boleto_ext = '.dat'

                                    self.processar_arquivo(
                                        temp_boleto,
                                        response_boleto.content,
                                        boleto_ext,
                                        f"boleto_{num_fatura}",
                                        empresa,
                                        nome_pasta_sharepoint,
                                        pasta_destino,
                                    )
                        except Exception as e:
                            self.logger.error(f"Erro ao processar documentos {site_nome} da fatura {num_fatura}: {str(e)}")

    def processar_arquivo(self, arquivo_temp, conteudo, extensao, nome_base, empresa, nome_pasta, pasta_local):
        """
        Processa um arquivo baixado, extraindo seu conteúdo se for ZIP e salvando no destino apropriado.
        """
        nome_arquivo = f"{nome_base}{extensao}"
        self.logger.info(f"Processando arquivo {nome_arquivo}")

        if extensao == '.zip':
            try:
                with zipfile.ZipFile(arquivo_temp, 'r') as zip_ref:
                    for zip_info in zip_ref.infolist():
                        with zip_ref.open(zip_info.filename) as file:
                            arquivo_conteudo = file.read()
                            nome_arquivo_extraido = zip_info.filename

                            if self.sharepoint_disponivel:
                                enviar_arquivo_para_sharepoint(
                                    arquivo_conteudo,
                                    nome_arquivo_extraido,
                                    empresa,
                                    nome_pasta,
                                    self.nome_ie,
                                )
                            else:
                                caminho_extraido = os.path.join(pasta_local, nome_arquivo_extraido)
                                with open(caminho_extraido, 'wb') as f:
                                    f.write(arquivo_conteudo)
                                self.logger.info(f"Arquivo extraído {nome_arquivo_extraido} salvo localmente!")

                self.logger.info(f"Arquivo ZIP {nome_base} processado com sucesso!")

            except Exception as e:
                self.logger.error(f"Erro ao descompactar o arquivo ZIP {nome_base}: {str(e)}")
                if self.sharepoint_disponivel:
                    enviar_arquivo_para_sharepoint(
                        conteudo,
                        nome_arquivo,
                        empresa,
                        nome_pasta,
                        self.nome_ie,
                    )
                else:
                    arquivo_final = os.path.join(pasta_local, nome_arquivo)
                    shutil.copy2(arquivo_temp, arquivo_final)
                    self.logger.info(f"Arquivo {nome_arquivo} salvo localmente como fallback")
        else:
            if self.sharepoint_disponivel:
                enviar_arquivo_para_sharepoint(
                    conteudo,
                    nome_arquivo,
                    empresa,
                    nome_pasta,
                    self.nome_ie,
                )
            else:
                arquivo_final = os.path.join(pasta_local, nome_arquivo)
                shutil.copy2(arquivo_temp, arquivo_final)
                self.logger.info(f"Arquivo {nome_arquivo} salvo localmente")

    def processar_site(self, site_nome):
        """
        Processa um site específico para todas as credenciais
        """
        self.logger.info(f"\n=== PROCESSANDO {site_nome} ===")

        if not self.credenciais:
            self.credenciais = carregar_credenciais()
            if not self.credenciais:
                self.logger.error("Não foi possível carregar as credenciais. Processo interrompido.")
                return

        for credencial in self.credenciais:
            tipo_empresa = credencial.get('empresa')  # AE, DE ou RE
            usuario = credencial.get('usuario') or credencial.get('email') or ''
            senha = credencial.get('senha') or credencial.get('password') or ''

            if not usuario or not senha:
                self.logger.error("Credencial inválida (faltando usuário/senha). Pulando...")
                continue

            sessao = self.login(site_nome, usuario, senha)
            if not sessao:
                self.logger.error(f"Não foi possível fazer login para {tipo_empresa}. Pulando...")
                continue

            resultado = self.pesquisar_faturas(site_nome, sessao)
            if not resultado:
                self.logger.error(f"Não foi possível pesquisar faturas para {tipo_empresa}. Pulando...")
                continue

            transmissoras = self.identificar_transmissoras(resultado)
            if not transmissoras:
                self.logger.error(f"Nenhuma transmissora identificada para {tipo_empresa}. Pulando...")
                continue

            for nome_transmissora, info in transmissoras.items():
                pasta_base = info['pasta_base']

                self.logger.info(f"\nProcessando {tipo_empresa} - {site_nome}: {nome_transmissora} (Pasta: {pasta_base})")
                self.logger.info("-" * 50)

                soup = BeautifulSoup(resultado, 'html.parser')
                transmissora_fieldset = None
                for fieldset in soup.find_all('fieldset'):
                    legend = fieldset.find('legend')
                    if legend and legend.text.strip() == nome_transmissora:
                        transmissora_fieldset = fieldset
                        break

                if not transmissora_fieldset:
                    self.logger.warning(f"Fieldset não encontrada para transmissora {nome_transmissora}. Pulando...")
                    continue

                novo_html = f"""
                <fieldset>
                    <legend>{nome_transmissora}</legend>
                    {transmissora_fieldset.find('table').prettify()}
                </fieldset>
                """

                tem_faturas = self.extrair_e_mostrar_transmissoras(site_nome, novo_html, pasta_base)
                if tem_faturas:
                    self.logger.info(f"\nIniciando downloads dos documentos {site_nome} para {nome_transmissora}...")
                    self.download_documentos(site_nome, sessao, novo_html, tipo_empresa, pasta_base)
                    self.logger.info(f"\nProcesso {site_nome} finalizado para {nome_transmissora} ({tipo_empresa} - {pasta_base})!")
                else:
                    self.logger.info(f"\nNenhuma fatura encontrada no {site_nome} para {nome_transmissora} ({tipo_empresa} - {pasta_base})!")

    def processar_todos_sites(self):
        """
        Processa todos os sites configurados na instância
        """
        for site_nome in self.sites:
            self.processar_site(site_nome)

        self.logger.info("\n=== PROCESSAMENTO DE TODOS OS SITES CONCLUÍDO ===")

    def get_credentials_for_group(self, group):
        """Retorna lista de credenciais que pertencem ao grupo especificado (RE/AE/DE)."""
        if not self.credenciais:
            self.credenciais = carregar_credenciais() or []
        return [c for c in (self.credenciais or []) if (c.get('empresa') or '').upper() == (group or '').upper()]

    def processar_por_empresas(self, periodo=None):
        """
        Processa o download das faturas com base em `Data/empresas.json`.

        Sequência:
        - Carrega o mapeamento de empresas (RE/AE/DE) a partir de `carregar_empresas()`
        - Para cada grupo e cada empresa listada, tenta logar com as credenciais do respectivo grupo
        - Pesquisa o período (padrão: mês anterior) e baixa os documentos apenas para a pasta/base correspondente à empresa
        """
        empresas = carregar_empresas()
        if not empresas:
            self.logger.error("Não foi possível carregar o arquivo de empresas. Abortando processamento por empresas.")
            return

        for grupo, lista_empresas in empresas.items():
            self.logger.info(f"\n=== Iniciando grupo {grupo} com {len(lista_empresas)} empresas ===")

            creds = self.get_credentials_for_group(grupo)
            if not creds:
                self.logger.warning(f"Nenhuma credencial encontrada para o grupo {grupo}. Pulando grupo.")
                continue

            # Para cada empresa do grupo, tentamos processar usando uma das credenciais
            for empresa in lista_empresas:
                codigo_empresa = empresa.get('codigo')
                nome_empresa = empresa.get('nome')
                self.logger.info(f"\n-- Processando empresa {nome_empresa} (codigo {codigo_empresa}) do grupo {grupo}")

                processado_com_sucesso = False

                for cred in creds:
                    usuario = cred.get('usuario') or cred.get('email') or ''
                    senha = cred.get('senha') or cred.get('password') or ''
                    if not usuario or not senha:
                        self.logger.warning("Credencial incompleta encontrada — pulando esta credencial.")
                        continue

                    sessao = self.login(self.nome_ie, usuario, senha)
                    if not sessao:
                        self.logger.warning(f"Login falhou para {usuario}. Tentando próxima credencial...")
                        continue

                    resultado = self.pesquisar_faturas(self.nome_ie, sessao, periodo)
                    if not resultado:
                        self.logger.warning(f"Pesquisa não retornou resultados usando {usuario}. Tentando próxima credencial...")
                        continue

                    transmissoras = self.identificar_transmissoras(resultado)
                    if not transmissoras:
                        self.logger.warning(f"Nenhuma transmissora identificada usando {usuario}.")
                        continue

                    # Procurar transmissoras que correspondam ao nome/pasta da empresa ou ao seu código
                    for nome_transmissora, info in transmissoras.items():
                        pasta_base = info.get('pasta_base')
                        codigo_ons = info.get('codigo_ons')
                        codigo_extra = info.get('codigo')

                        matches = False
                        if pasta_base and pasta_base == nome_empresa:
                            matches = True
                        if codigo_ons and codigo_empresa and codigo_ons == codigo_empresa:
                            matches = True
                        if codigo_extra and codigo_empresa and codigo_extra == codigo_empresa:
                            matches = True

                        if not matches:
                            continue

                        # Encontramos transmissora relevante — montar novo HTML contendo apenas a tabela
                        soup = BeautifulSoup(resultado, 'html.parser')
                        transmissora_fieldset = None
                        for fieldset in soup.find_all('fieldset'):
                            legend = fieldset.find('legend')
                            if legend and legend.text.strip() == nome_transmissora:
                                transmissora_fieldset = fieldset
                                break

                        if not transmissora_fieldset:
                            self.logger.warning(f"Fieldset não encontrada para {nome_transmissora}. Pulando...")
                            continue

                        novo_html = f"""
                        <fieldset>
                            <legend>{nome_transmissora}</legend>
                            {transmissora_fieldset.find('table').prettify()}
                        </fieldset>
                        """

                        tem_faturas = self.extrair_e_mostrar_transmissoras(self.nome_ie, novo_html, pasta_base)
                        if tem_faturas:
                            self.logger.info(f"Iniciando downloads para {nome_transmissora} ({nome_empresa})...")
                            self.download_documentos(self.nome_ie, sessao, novo_html, grupo, pasta_base)
                            processado_com_sucesso = True
                        else:
                            self.logger.info(f"Nenhuma fatura encontrada para {nome_transmissora} ({nome_empresa}).")

                    # Se já processamos com sucesso para essa empresa, sair do loop de credenciais
                    if processado_com_sucesso:
                        self.logger.info(f"Empresa {nome_empresa} processada com sucesso. Avançando para a próxima empresa.")
                        break
                    else:
                        self.logger.info(f"Não foram encontrados/baixados títulos para {nome_empresa} usando {usuario}. Tentando próxima credencial...")

                if not processado_com_sucesso:
                    self.logger.warning(f"Falha ao processar empresa {nome_empresa} com todas as credenciais disponíveis do grupo {grupo}.")

        self.logger.info("\n=== PROCESSAMENTO POR EMPRESAS CONCLUÍDO ===")
