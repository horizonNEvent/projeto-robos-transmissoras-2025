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
import argparse
import urllib3
import sqlite3

# Desabilita avisos de SSL inseguro
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuração de logging base
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RobotBaseIE")

# Diretórios
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(WORKSPACE_ROOT, 'Data')
EMPRESAS_JSON = os.path.join(DATA_DIR, 'empresas.json')
DB_PATH = os.path.join(WORKSPACE_ROOT, 'sql_app.db')

def get_periodo_padrao():
    hoje = datetime.now()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_mes = primeiro_dia_mes_atual - timedelta(days=1)
    return f"{ultimo_mes.year}|{str(ultimo_mes.month).zfill(2)}"

def carregar_empresas():
    try:
        if not os.path.exists(EMPRESAS_JSON):
            return None
        with open(EMPRESAS_JSON, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            empresas_formatadas = {}
            for empresa, codigos in dados.items():
                empresas_formatadas[empresa] = []
                if isinstance(codigos, dict):
                    for codigo, nome in codigos.items():
                        if codigo and nome: # Evita chaves vazias ou nulas
                            empresas_formatadas[empresa].append({"codigo": str(codigo), "nome": nome})
                elif isinstance(codigos, list):
                    for item in codigos:
                        if isinstance(item, dict):
                            for codigo, nome in item.items():
                                empresas_formatadas[empresa].append({"codigo": str(codigo), "nome": nome})
            return empresas_formatadas
    except Exception as e:
        logger.error(f"Erro ao carregar empresas: {e}")
        return None

def carregar_credenciais():
    creds = []
    try:
        if not os.path.exists(DB_PATH):
            return creds
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT label, username, password, agents_json, base FROM robot_configs WHERE robot_type = 'WEBIE' AND active = 1")
        rows = cursor.fetchall()
        for row in rows:
            creds.append({
                "empresa": row[0],
                "usuario": row[1],
                "senha": row[2],
                "agentes": json.loads(row[3] or '{}'),
                "base": row[4]
            })
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao carregar credenciais do banco: {e}")
    return creds

class RobotBaseIE:
    def __init__(self, nome_ie, url_ie, mapeamento_codigos=None):
        self.nome_ie = nome_ie
        self.base_dir = os.path.join(r"C:\Users\Bruno\Downloads\TUST", nome_ie)
        self.url_ie = url_ie
        self.mapeamento_codigos = mapeamento_codigos or {}
        self.logger = logging.getLogger(nome_ie)
        os.makedirs(self.base_dir, exist_ok=True)

    def login(self, usuario, senha):
        url = f"{self.url_ie}/login.asp"
        dados_login = {'usuario': usuario, 'senha': senha}
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        try:
            sessao = requests.Session()
            resposta = sessao.post(url, data=dados_login, headers=headers, verify=False, timeout=30)
            if resposta.status_code == 200 and "usuario" not in resposta.text.lower(): # Verificação simples de erro no HTML
                 if "esqueceu sua senha" not in resposta.text.lower():
                    self.logger.info(f"Login {self.nome_ie} OK: {usuario}")
                    return sessao
            self.logger.error(f"Falha login {self.nome_ie} para {usuario}")
            return None
        except Exception as e:
            self.logger.error(f"Erro login {self.nome_ie}: {e}")
            return None

    def pesquisar_faturas(self, sessao, periodo=None):
        if periodo is None:
            periodo = get_periodo_padrao()
        url_rb = f"{self.url_ie}/RB.asp"
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            sessao.get(url_rb, headers=headers, verify=False)
            dados_pesquisa = {'data': periodo}
            resposta = sessao.post(url_rb, data=dados_pesquisa, headers=headers, verify=False, timeout=30)
            if resposta.status_code == 200:
                return resposta.text
            return None
        except Exception as e:
            self.logger.error(f"Erro pesquisa {self.nome_ie}: {e}")
            return None

    def identificar_transmissoras(self, html, filtro_agente=None):
        soup = BeautifulSoup(html, 'html.parser')
        transmissoras_identificadas = {}
        empresas = carregar_empresas()
        fieldsets = soup.find_all('fieldset')

        for fieldset in fieldsets:
            legend = fieldset.find('legend')
            if not legend: continue
            nome_transmissora = legend.text.strip()
            
            tabela = fieldset.find('table')
            if not tabela: continue
            
            linhas = tabela.find_all('tr')[1:]
            if not linhas: continue

            # Pega dados da primeira linha válida
            dados_linha = None
            for r in linhas:
                cols = r.find_all('td')
                if len(cols) >= 4 and 'Total' not in cols[0].text:
                    dados_linha = cols
                    break
            
            if not dados_linha: continue
            
            codigo_ons = dados_linha[1].text.strip()
            
            # Filtro de agente ONS
            if filtro_agente and str(filtro_agente) != str(codigo_ons):
                continue

            empreendimento = dados_linha[0].text.strip()
            match = re.search(r'^(\d+)', empreendimento)
            codigo_empreendimento = match.group(1) if match else 'desconhecido'

            pasta_base = None
            if codigo_ons in self.mapeamento_codigos:
                pasta_base = self.mapeamento_codigos[codigo_ons]
            elif empresas:
                for _, lista in empresas.items():
                    for item in lista:
                        if item.get('codigo') == codigo_ons:
                            pasta_base = item.get('nome')
                            break
                    if pasta_base: break
            
            if not pasta_base:
                pasta_base = re.sub(r'[^\w\s]', '', nome_transmissora).replace(' ', '_')

            transmissoras_identificadas[nome_transmissora] = {
                'codigo_ons': codigo_ons,
                'codigo_empreendimento': codigo_empreendimento,
                'pasta_base': pasta_base,
                'fieldset_html': str(fieldset)
            }
        return transmissoras_identificadas

    def download_documentos(self, sessao, html_fieldset, empresa_grupo, pasta_base):
        soup = BeautifulSoup(html_fieldset, 'html.parser')
        tabela = soup.find('table')
        if not tabela: return

        linhas = tabela.find_all('tr')[1:]
        for linha in linhas:
            cols = linha.find_all('td')
            if len(cols) < 3: continue
            
            empreendimento = cols[0].text.strip()
            if not empreendimento or 'Total' in empreendimento: continue
            
            # Tenta pegar código do Nome (col 0)
            match = re.search(r'^(\d+)', empreendimento)
            cod_empr = match.group(1) if match else None

            # Se não achou no nome, usa Coluna 1 + Nome para garantir unicidade
            # Isso evita agrupar contratos diferentes que compartilham o mesmo código de agente
            if not cod_empr:
                nome_sanitizado = re.sub(r'[^\w\s-]', '', empreendimento).strip().replace(' ', '_')
                if len(cols) > 1:
                    cand = cols[1].text.strip()
                    if cand.isdigit():
                        cod_empr = f"{cand}_{nome_sanitizado}"
                
                if not cod_empr:
                    cod_empr = f"Desconhecido_{nome_sanitizado}"
            
            num_fatura = cols[2].text.strip()
            
            pasta_destino = os.path.join(self.base_dir, empresa_grupo, pasta_base, f"EMC_{cod_empr}")
            os.makedirs(pasta_destino, exist_ok=True)

            base_url = f"{self.url_ie}/download.asp"
            
            # XML
            try:
                url_fatura = f"{base_url}?mode=admin&arquivo=zip&tipo=xml&num_fatura={num_fatura}"
                res = sessao.get(url_fatura, verify=False, timeout=60)
                if res.status_code == 200 and res.content:
                    self.salvar_e_extrair(res.content, f"fatura_{num_fatura}", pasta_destino)
            except Exception as e:
                self.logger.error(f"Erro download XML {num_fatura}: {e}")

            # Boleto
            try:
                url_boleto = f"{base_url}?mode=admin&tipo=boleto&arquivo=zip&num_fatura={num_fatura}"
                res_b = sessao.get(url_boleto, verify=False, timeout=60)
                if res_b.status_code == 200 and res_b.content:
                    self.salvar_e_extrair(res_b.content, f"boleto_{num_fatura}", pasta_destino)
            except Exception as e:
                self.logger.error(f"Erro download Boleto {num_fatura}: {e}")

    def salvar_e_extrair(self, conteudo, nome_base, pasta_destino):
        if conteudo.startswith(b'PK'):
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(conteudo)
                tmp_path = tmp.name
            try:
                with zipfile.ZipFile(tmp_path, 'r') as z:
                    for info in z.infolist():
                        with z.open(info.filename) as f:
                            with open(os.path.join(pasta_destino, info.filename), 'wb') as dest:
                                dest.write(f.read())
                self.logger.info(f"Extraído ZIP {nome_base} em {pasta_destino}")
            finally:
                if os.path.exists(tmp_path): os.remove(tmp_path)
        else:
            ext = '.xml' if b'<?xml' in conteudo[:100] else '.pdf' if b'%PDF' in conteudo[:100] else '.dat'
            with open(os.path.join(pasta_destino, f"{nome_base}{ext}"), 'wb') as f:
                f.write(conteudo)
            self.logger.info(f"Salvo {nome_base}{ext}")

    def run(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--empresa", help="Nome da empresa para filtrar (RE/AE/DE)")
        parser.add_argument("--agente", help="Código ONS do agente para filtrar")
        parser.add_argument("--user", help="Usuário para login direto")
        parser.add_argument("--password", help="Senha para login direto")
        args = parser.parse_args()

        empresas_config = carregar_empresas() or {}
        todo_credenciais = carregar_credenciais()

        if args.user and args.password:
            self.logger.info(f"Usando login manual para {args.user}")
            
            filtro_agentes = []
            if args.agente:
                filtro_agentes = [a.strip() for a in str(args.agente).split(',')]
            
            self.logger.info(f"Iniciando login {self.nome_ie} direto para {args.user}")
            sessao = self.login(args.user, args.password)
            if sessao:
                self.logger.info(f"Login OK para {args.user}")
                html = self.pesquisar_faturas(sessao)
                if html:
                    transmissoras = self.identificar_transmissoras(html)
                    self.logger.info(f"Identificadas {len(transmissoras)} transmissoras no site")
                    
                    for nome_transmissora, info in transmissoras.items():
                        cod_ons = str(info['codigo_ons']).strip()
                        # Filtros
                        if filtro_agentes and cod_ons not in filtro_agentes: continue
                        
                        final_grupo = args.empresa or "GERAL"
                        self.logger.info(f"Processando: {nome_transmissora} (ONS: {cod_ons}) em {final_grupo}")
                        self.download_documentos(sessao, info['fieldset_html'], final_grupo, info['pasta_base'])
                else:
                    self.logger.error("Falha ao carregar faturas após login.")
            else:
                 self.logger.error(f"Falha login para {args.user}")
            return

        # Processamento via Banco de Dados
        for cred in todo_credenciais:
            # Filtro de Empresa/Label do painel (Robusto)
            input_empresa = (args.empresa or "").strip().upper()
            cred_empresa = (cred['empresa'] or "").strip().upper()
            cred_base = (cred['base'] or "").strip().upper()

            if input_empresa and input_empresa != cred_empresa and input_empresa != cred_base:
                continue
            
            self.logger.info(f"--- Processando Credencial: {cred['empresa']} ({cred['usuario']}) ---")
            
            # Mescla agentes específicos desta credencial no mapeamento global se não houver
            for cod, nome in cred['agentes'].items():
                if cred['base'] not in empresas_config: empresas_config[cred['base']] = []
                # Evita duplicidade
                if not any(a['codigo'] == str(cod) for a in empresas_config[cred['base']]):
                    empresas_config[cred['base']].append({"codigo": str(cod), "nome": nome})

            sessao = self.login(cred['usuario'], cred['senha'])
            if sessao:
                self.logger.info(f"Login WebIERIACHOGRANDE OK para {cred['empresa']}")
                
                html = self.pesquisar_faturas(sessao)
                if html:
                    transmissoras_site = self.identificar_transmissoras(html)
                    
                    # Agentes que devemos processar para ESTA credencial
                    meus_agentes = cred['agentes']
                    
                    filtro_agentes = []
                    if args.agente:
                        filtro_agentes = [a.strip() for a in str(args.agente).split(',')]

                    for nome_site, info in transmissoras_site.items():
                        cod_ons = str(info['codigo_ons']).strip()
                        
                        # Filtro de Agente via Linha de Comando
                        if filtro_agentes and cod_ons not in filtro_agentes:
                            continue
                            
                        # Verifica se este agente pertence a esta credencial ou se estamos em modo "Geral"
                        # Se meus_agentes estiver vazio, assume que processa tudo que encontrar com esse login
                        if meus_agentes and cod_ons not in meus_agentes:
                            continue
                        
                        final_grupo_db = cred['base'] or cred['empresa'] or "GERAL"
                        self.logger.info(f"Iniciando download para: {nome_site} (ONS: {cod_ons}) em {final_grupo_db}")
                        self.download_documentos(sessao, info['fieldset_html'], final_grupo_db, info['pasta_base'])
                else:
                    self.logger.error(f"Falha ao carregar faturas para {cred['empresa']}")
            else:
                self.logger.error(f"Falha login para {cred['empresa']}")
