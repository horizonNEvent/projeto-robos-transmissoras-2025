import os
import sqlite3
import glob
import logging
import re
from xml.etree import ElementTree

# Configuração de logging independente para este módulo
logger = logging.getLogger("XMLUtils")

# Caminho para o Banco de Dados (assumindo mesma estrutura do RobotBaseIE)
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(WORKSPACE_ROOT, 'sql_app.db')

def buscar_transmissora_por_cnpj(cnpj):
    """
    Busca uma transmissora no banco de dados pelo CNPJ.
    Retorna um dicionário com os dados ou None se não encontrar.
    """
    if not cnpj:
        return None
        
    try:
        # Remove formatação do CNPJ para busca
        cnpj_limpo = re.sub(r'\D', '', str(cnpj))
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Tenta buscar pelo CNPJ formatado ou limpo
        cursor.execute("SELECT codigo_ons, sigla, nome, grupo FROM transmissora WHERE replace(replace(replace(cnpj, '.', ''), '/', ''), '-', '') = ?", (cnpj_limpo,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "codigo_ons": row[0],
                "sigla": row[1],
                "nome": row[2],
                "grupo": row[3]
            }
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar transmissora no DB: {e}")
        return None

def ler_cnpj_do_xml(xml_path):
    """
    Lê o arquivo XML e extrai o CNPJ do emitente.
    """
    try:
        tree = ElementTree.parse(xml_path)
        root = tree.getroot()
        
        # Namespaces comuns em NFe
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        
        # Tenta encontrar o CNPJ do emitente
        # Estrutura padrão: nfeProc -> NFe -> infNFe -> emit -> CNPJ
        # Mas o root pode variar dependendo se é nfeProc ou NFe direto
        
        cnpj = None
        
        # Tenta com namespace
        emit = root.find('.//nfe:emit', ns)
        if emit is None:
            # Tenta sem namespace (ou namespace default)
            emit = root.find('.//emit')
            
        if emit is not None:
            cnpj_tag = emit.find('nfe:CNPJ', ns)
            if cnpj_tag is None:
                cnpj_tag = emit.find('CNPJ')
                
            if cnpj_tag is not None:
                cnpj = cnpj_tag.text
                
        return cnpj
    except Exception as e:
        logger.error(f"Erro ao ler XML {os.path.basename(xml_path)}: {e}")
        return None

# Fallback removido daqui para ser passado via parâmetro
# FIX_MANUAL = {}

def buscar_transmissora_por_codigo(codigo_ons, fixes=None):
    """
    Busca uma transmissora no banco de dados pelo Código ONS.
    Args:
        fixes (dict, optional): Dicionário de correções manuais { 'CODIGO': {'codigo_ons':..., 'sigla':...} }
    """
    if not codigo_ons: return None
    
    # 1. Checa hardcoded fix passado via parâmetro
    if fixes and str(codigo_ons) in fixes:
        return fixes[str(codigo_ons)]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT codigo_ons, sigla, nome, grupo FROM transmissora WHERE codigo_ons = ?", (str(codigo_ons),))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"codigo_ons": row[0], "sigla": row[1], "nome": row[2], "grupo": row[3]}
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar transmissora por código {codigo_ons}: {e}")
        return None

def renomear_pasta_baseado_no_xml(pasta_alvo, fixes=None):
    """
    Identifica a transmissora da pasta e a renomeia.
    Args:
        fixes (dict, optional): Dicionário de correções manuais para códigos específicos.
    """
    if not os.path.exists(pasta_alvo):
        logger.warning(f"Pasta não existe: {pasta_alvo}")
        return pasta_alvo

    nome_pasta_atual = os.path.basename(pasta_alvo)
    info_transmissora = None
    
    # 1. Tenta identificar pelo código na pasta (EMC_XXXX)
    match_codigo = re.search(r'EMC_(\d+)', nome_pasta_atual)
    if match_codigo:
        codigo_da_pasta = match_codigo.group(1)
        info_transmissora = buscar_transmissora_por_codigo(codigo_da_pasta, fixes)
        if info_transmissora:
            logger.info(f"Identificado pelo código da pasta {codigo_da_pasta}: {info_transmissora['sigla']}")

    # 2. Se não achou pelo código, tenta pelo XML (CNPJ)
    if not info_transmissora:
        xml_files = glob.glob(os.path.join(pasta_alvo, "*.xml"))
        if xml_files:
            for xml in xml_files:
                cnpj = ler_cnpj_do_xml(xml)
                if cnpj:
                    info_encontrada = buscar_transmissora_por_cnpj(cnpj)
                    if info_encontrada:
                        # Verifica conflito entre Código da Pasta e Código do CNPJ
                        # Se a pasta diz 1081 e o CNPJ diz 1099, respeita o 1081 da pasta!
                        match_codigo = re.search(r'EMC_(\d+)', nome_pasta_atual)
                        if match_codigo:
                            codigo_da_pasta = match_codigo.group(1)
                            if str(info_encontrada['codigo_ons']) != str(codigo_da_pasta):
                                logger.warning(f"Conflito! Pasta {codigo_da_pasta} vs CNPJ {info_encontrada['codigo_ons']}. Mantendo {codigo_da_pasta}.")
                                info_encontrada['codigo_ons'] = codigo_da_pasta
                                # Opcional: Adicionar sufixo para indicar que foi derivado
                                # info_encontrada['sigla'] += f"_{codigo_da_pasta}" 
                        
                        info_transmissora = info_encontrada
                        logger.info(f"Identificação por CNPJ {cnpj}: {info_transmissora['sigla']} (ONS final: {info_transmissora['codigo_ons']})")
                        break
    
    if info_transmissora:
        ons = info_transmissora['codigo_ons']
        sigla = info_transmissora['sigla'] or "DESCONHECIDO"
        
        # Novo nome da pasta
        novo_nome = f"{ons}_{sigla}"
        nova_pasta = os.path.join(os.path.dirname(pasta_alvo), novo_nome)
        
        # Evita renomear se já estiver com o nome correto
        if novo_nome == nome_pasta_atual:
            return pasta_alvo

        # Se já existe a pasta destino, tenta mesclar
        if os.path.exists(nova_pasta) and nova_pasta != pasta_alvo:
            logger.warning(f"A pasta destino {nova_pasta} já existe. Tentando mesclar arquivos.")
            for item in os.listdir(pasta_alvo):
                s = os.path.join(pasta_alvo, item)
                d = os.path.join(nova_pasta, item)
                if not os.path.exists(d):
                    try:
                        os.rename(s, d)
                    except Exception as e:
                        logger.error(f"Erro ao mover {item}: {e}")
            try:
                os.rmdir(pasta_alvo)
                return nova_pasta
            except:
                logger.warning(f"Não foi possível remover a pasta antiga {pasta_alvo} (pode não estar vazia).")
                pass
        else:
            try:
                os.rename(pasta_alvo, nova_pasta)
                logger.info(f"Pasta renomeada de {nome_pasta_atual} para {novo_nome}")
                return nova_pasta
            except Exception as e:
                logger.error(f"Erro ao renomear pasta: {e}")
                
    else:
        logger.warning(f"Não foi possível identificar transmissora para {pasta_alvo}")
        
    return pasta_alvo
