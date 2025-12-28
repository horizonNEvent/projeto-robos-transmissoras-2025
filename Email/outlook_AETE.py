import os
import requests
import email
import imaplib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.header import decode_header
import re
import json

# Configurações de autenticação OAuth2
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
TENANT_ID = os.getenv("AZURE_TENANT_ID")

# Caminhos dos arquivos de configuração
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PATH_TUST = os.path.join(BASE_DIR, "tust.json")
PATH_MAPEAMENTO = os.path.join(BASE_DIR, "mapeamento_cnpj.json")
PATH_REMETENTES = os.path.join(BASE_DIR, "remetentes.json")

def carregar_json(caminho):
    """Carrega um arquivo JSON e retorna seu conteúdo"""
    try:
        if os.path.exists(caminho):
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Erro ao carregar {caminho}: {e}")
        return None

# Mapeamento de CNPJs de transmissoras para nomes (carregado via JSON)
TRANSMISSORAS = carregar_json(PATH_MAPEAMENTO) or {}

# Lista de remetentes autorizados
REMETENTES_AUTORIZADOS = carregar_json(PATH_REMETENTES) or []

# Mapeamento de CNPJs para siglas de empresas (AETE / Anemus)
EMPRESAS = {
    "29481536000158": {"sigla": "Anemus_I", "nome": "Anemus_I"},
    "29492546000199": {"sigla": "Anemus_II", "nome": "Anemus_II"}, 
    "38350307000195": {"sigla": "Anemus_III", "nome": "Anemus_III"},
}

# Configurações de contas de email - Focando apenas em AETE
CONTAS_EMAIL = {
    "AETE": {
        "email": "tust@anemuswind.com.br",
        "cnpjs": list(EMPRESAS.keys())
    }
}

# Configurações do servidor IMAP
IMAP_SERVER = "outlook.office365.com"
IMAP_PORT = 993

# Configurações do diretório para salvar anexos
PASTA_DESTINO_BASE = os.path.join(BASE_DIR, "ANEXOS_DOWNLOAD")

def obter_token_oauth2():
    """Obtém um token OAuth2 usando o fluxo client_credentials"""
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/token"
    
    dados = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'resource': 'https://outlook.office.com'
    }
    
    resposta = requests.post(url, data=dados)
    
    if resposta.status_code == 200:
        return resposta.json().get('access_token')
    else:
        print(f"Erro ao obter token: {resposta.status_code} - {resposta.text}")
        return None

def extrair_info_xml(caminho_arquivo):
    """Extrai informações do XML da NF-e"""
    try:
        # Registrar os namespaces
        namespaces = {
            'nfe': 'http://www.portalfiscal.inf.br/nfe'
        }
        
        # Analisar o XML
        tree = ET.parse(caminho_arquivo)
        root = tree.getroot()
        
        # Procurar elementos relevantes
        # Corrigindo os avisos de depreciação
        dest_element = root.find('.//nfe:dest', namespaces)
        if dest_element is None:
            dest_element = root.find('.//dest')
            
        emit_element = root.find('.//nfe:emit', namespaces)
        if emit_element is None:
            emit_element = root.find('.//emit')
        
        if dest_element is None or emit_element is None:
            print(f"Estrutura XML não reconhecida em: {caminho_arquivo}")
            return None, None, None, None, None
        
        # Extrair CNPJ do destinatário
        cnpj_dest_element = dest_element.find('.//nfe:CNPJ', namespaces)
        if cnpj_dest_element is None:
            cnpj_dest_element = dest_element.find('CNPJ')
        cnpj_dest = cnpj_dest_element.text if cnpj_dest_element is not None else None
        
        # Extrair nome do destinatário
        nome_dest_element = dest_element.find('.//nfe:xNome', namespaces)
        if nome_dest_element is None:
            nome_dest_element = dest_element.find('xNome')
        nome_dest = nome_dest_element.text if nome_dest_element is not None else None
        
        # Extrair CNPJ do emitente
        cnpj_emit_element = emit_element.find('.//nfe:CNPJ', namespaces)
        if cnpj_emit_element is None:
            cnpj_emit_element = emit_element.find('CNPJ')
        cnpj_emit = cnpj_emit_element.text if cnpj_emit_element is not None else None
        
        # Extrair nome do emitente
        nome_emit_element = emit_element.find('.//nfe:xNome', namespaces)
        if nome_emit_element is None:
            nome_emit_element = emit_element.find('xNome')
        nome_emit = nome_emit_element.text if nome_emit_element is not None else None
        
        # Extrair informações adicionais para identificar a Narandiba específica
        info_adicional = ""
        
        # Tentar encontrar informações no campo de descrição do produto
        produtos = root.findall('.//nfe:det', namespaces) or root.findall('.//det')
        if produtos:
            for produto in produtos:
                desc_element = produto.find('.//nfe:xProd', namespaces) or produto.find('.//xProd')
                if desc_element is not None and desc_element.text:
                    desc = desc_element.text
                    if "BRUMADO" in desc.upper():
                        info_adicional = "BRUMADO II"
                        break
                    elif "EXTREMOZ" in desc.upper():
                        info_adicional = "EXTREMOZ II"
                        break
        
        # Se não encontrou nas descrições, tentar no campo de informações complementares
        if not info_adicional:
            info_comp_element = root.find('.//nfe:infAdic/nfe:infCpl', namespaces) or root.find('.//infAdic/infCpl')
            if info_comp_element is not None and info_comp_element.text:
                info_comp = info_comp_element.text
                if "BRUMADO" in info_comp.upper():
                    info_adicional = "BRUMADO II"
                elif "EXTREMOZ" in info_comp.upper():
                    info_adicional = "EXTREMOZ II"
        
        print(f"Informações extraídas: Destinatário: {cnpj_dest} ({nome_dest}), Emitente: {cnpj_emit} ({nome_emit}), Info Adicional: {info_adicional}")
        return cnpj_dest, nome_dest, cnpj_emit, nome_emit, info_adicional
    
    except Exception as e:
        print(f"Erro ao analisar XML {caminho_arquivo}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, None, None, None

def processar_anexo_xml(caminho_original, nome_arquivo):
    """Processa um arquivo XML, extraindo informações e movendo para a pasta da transmissora"""
    # Extrair informações do XML
    cnpj_dest, nome_dest, cnpj_emit, nome_emit, info_adicional = extrair_info_xml(caminho_original)
    
    if cnpj_emit and cnpj_dest:
        # Verificar se o CNPJ do destinatário está no mapeamento de empresas AETE
        if cnpj_dest not in EMPRESAS:
            print(f"CNPJ Destinatário {cnpj_dest} não pertence às empresas AETE selecionadas. Ignorando.")
            return None
            
        nome_empresa_pasta = EMPRESAS[cnpj_dest]["sigla"]
        nome_empresa_arquivo = nome_empresa_pasta
        
        # Determinar o nome da transmissora
        nome_pasta_transmissora = None
        
        # Caso especial para Narandiba (mantido pois tem lógica de subprojeto)
        if cnpj_emit == "10337920000153":  # CNPJ da Narandiba
            if info_adicional == "BRUMADO II":
                nome_pasta_transmissora = "NARANDIBA (SE BRUMADO II)"
            elif info_adicional == "EXTREMOZ II":
                nome_pasta_transmissora = "NARANDIBA (SE EXTREMOZ II)"
            else:
                nome_pasta_transmissora = "NARANDIBA"
        # Verificar se o CNPJ está no dicionário de transmissoras carregado do JSON
        elif cnpj_emit in TRANSMISSORAS:
            nome_pasta_transmissora = TRANSMISSORAS[cnpj_emit]
        # Verificar se o nome contém "afluent" (case insensitive)
        elif nome_emit and "afluent" in nome_emit.lower():
            nome_pasta_transmissora = "AFLUENTE"
        else:
            # Para outras transmissoras, usar o nome do emitente formatado
            nome_pasta_transmissora = nome_emit.replace("/", "-").replace("\\", "-").strip()
            print(f"Nova transmissora detectada e mapeada pelo nome: {cnpj_emit} - {nome_emit}")
        
        # Criar pasta para a empresa se não existir
        pasta_empresa = os.path.join(PASTA_DESTINO_BASE, nome_empresa_pasta)
        if not os.path.exists(pasta_empresa):
            os.makedirs(pasta_empresa)
        
        # Criar pasta para a transmissora dentro da pasta da empresa
        pasta_transmissora = os.path.join(pasta_empresa, nome_pasta_transmissora)
        if not os.path.exists(pasta_transmissora):
            os.makedirs(pasta_transmissora)
        
        # Criar novo nome de arquivo com o nome da empresa destinatária
        _, extensao = os.path.splitext(nome_arquivo)
        novo_nome_arquivo = f"{nome_empresa_arquivo}{extensao}"
        
        # Caminho completo do novo arquivo
        novo_caminho = os.path.join(pasta_transmissora, novo_nome_arquivo)
        
        # Verificar se o arquivo já existe e adicionar sequencial se necessário
        if os.path.exists(novo_caminho):
            contador = 1
            while True:
                novo_nome_arquivo = f"{nome_empresa_arquivo}_{contador}{extensao}"
                novo_caminho = os.path.join(pasta_transmissora, novo_nome_arquivo)
                if not os.path.exists(novo_caminho):
                    break
                contador += 1
        
        try:
            # Mover arquivo
            os.rename(caminho_original, novo_caminho)
            print(f"Arquivo de interesse AETE processado: {novo_caminho}")
            return novo_caminho
        except Exception as e:
            print(f"Erro ao mover arquivo: {str(e)}")
            import shutil
            try:
                shutil.copy2(caminho_original, novo_caminho)
                os.remove(caminho_original)
                return novo_caminho
            except:
                return caminho_original
    
    return None


def processar_anexo_relacionado(caminho_original, nome_arquivo, caminho_xml):
    """Processa um arquivo relacionado (PDF, etc) movendo para a mesma pasta do XML"""
    if caminho_xml and caminho_xml != caminho_original:
        pasta_destino = os.path.dirname(caminho_xml)
        nome_base, extensao = os.path.splitext(nome_arquivo)
        
        # Usar o mesmo prefixo do XML
        prefixo = os.path.basename(caminho_xml).split('_')[0]
        novo_nome_arquivo = f"{prefixo}_{nome_base}{extensao}"
        
        novo_caminho = os.path.join(pasta_destino, novo_nome_arquivo)
        
        # Mover arquivo
        os.rename(caminho_original, novo_caminho)
        
        print(f"Arquivo relacionado movido para: {novo_caminho}")
        return novo_caminho
    
    return caminho_original

def parse_email_date(date_str):
    """Tenta fazer o parse da data do email em diferentes formatos"""
    # Remover texto entre parênteses, como '(INDIA)'
    date_str = re.sub(r'\s*\([^)]*\)', '', date_str).strip()
    
    formatos = [
        "%a, %d %b %Y %H:%M:%S %z",  # Formato padrão: 'Fri, 7 Mar 2025 14:37:51 -0300'
        "%d %b %Y %H:%M:%S %z",      # Formato alternativo: '7 Mar 2025 14:37:51 -0300'
        "%a, %d %b %Y %H:%M:%S",     # Sem timezone
        "%d %b %Y %H:%M:%S"          # Sem timezone e sem dia da semana
    ]
    
    for formato in formatos:
        try:
            return datetime.strptime(date_str, formato)
        except ValueError:
            continue
    
    # Se nenhum formato funcionar, tenta remover o timezone e fazer o parse
    try:
        # Remove o timezone (últimos 6 caracteres, ex: '-0300')
        if '+' in date_str or '-' in date_str:
            # Encontrar a posição do último + ou -
            pos_plus = date_str.rfind('+')
            pos_minus = date_str.rfind('-')
            
            # Pegar a posição que vier depois (ou -1 se não existir)
            pos = max(pos_plus, pos_minus)
            
            if pos > 0:
                # Extrair a parte antes do timezone
                date_str_sem_tz = date_str[:pos].strip()
                return datetime.strptime(date_str_sem_tz, "%a, %d %b %Y %H:%M:%S")
        
        # Tentar sem extrair o timezone
        return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
    except ValueError:
        raise ValueError(f"Não foi possível fazer o parse da data: {date_str}")

def baixar_anexos(conta_nome=None):
    """
    Baixa todos os anexos de emails dos últimos 30 dias do remetente especificado.
    Organiza os anexos por pasta de email (todos os anexos de um email na mesma pasta).
    """
    # Criar pasta de destino base se não existir
    if not os.path.exists(PASTA_DESTINO_BASE):
        os.makedirs(PASTA_DESTINO_BASE)
    
    # Determinar quais contas processar
    contas_para_processar = {}
    if conta_nome and conta_nome in CONTAS_EMAIL:
        contas_para_processar[conta_nome] = CONTAS_EMAIL[conta_nome]
    else:
        contas_para_processar = CONTAS_EMAIL
    
    # Processar cada conta
    for nome_conta, config_conta in contas_para_processar.items():
        email_conta = config_conta["email"]
        
        print(f"\n=== Processando conta: {nome_conta} ({email_conta}) ===")
        
        # Obter token OAuth2
        print("Obtendo token de autenticação OAuth2...")
        token = obter_token_oauth2()
        
        if not token:
            print("Falha ao obter token de autenticação.")
            continue
        
        try:
            # Conectar ao servidor IMAP
            print(f"Conectando ao servidor IMAP {IMAP_SERVER}...")
            imap = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            
            # Autenticar com OAuth2
            auth_string = f'user={email_conta}\x01auth=Bearer {token}\x01\x01'
            imap.authenticate('XOAUTH2', lambda x: auth_string)
            
            # Selecionar a caixa de entrada
            imap.select('INBOX')
            
            # Calcular data do primeiro dia do mês atual para "faturas desse mês"
            hoje = datetime.now()
            primeiro_dia_mes = hoje.replace(day=1)
            data_inicial = primeiro_dia_mes.strftime("%d-%b-%Y")
            
            # Buscar emails de todos os remetentes autorizados
            print(f"Buscando emails dos remetentes autorizados desde {data_inicial}...")
            
            ids_mensagens = []
            for remetente in REMETENTES_AUTORIZADOS:
                status, mensagens = imap.search(None, f'(SINCE "{data_inicial}" FROM "{remetente}")')
                if status == 'OK' and mensagens[0]:
                    ids_mensagens.extend(mensagens[0].split())
            
            # Remover IDs duplicados e ordenar
            ids_mensagens = sorted(list(set(ids_mensagens)))
            
            contador_emails = 0
            contador_anexos = 0
            
            if not ids_mensagens:
                print("Nenhum email encontrado para os remetentes autorizados.")
            
            # Processar cada mensagem
            for id_mensagem in ids_mensagens:
                contador_emails += 1
                
                # Buscar a mensagem completa
                status, dados = imap.fetch(id_mensagem, '(RFC822)')
                if status != 'OK':
                    continue
                    
                mensagem_raw = dados[0][1]
                mensagem = email.message_from_bytes(mensagem_raw)
                
                # Obter assunto e data
                assunto_header = decode_header(mensagem.get('Subject', 'Sem Assunto'))[0]
                assunto = assunto_header[0]
                encoding = assunto_header[1]
                
                if isinstance(assunto, bytes):
                    try:
                        assunto = assunto.decode(encoding if encoding else 'utf-8', errors='replace')
                    except:
                        assunto = assunto.decode('latin-1', errors='replace')
                
                # Usar a nova função para fazer o parse da data
                try:
                    data_recebimento = parse_email_date(mensagem['Date'])
                    data_formatada = data_recebimento.strftime("%Y-%m-%d")
                except:
                    data_formatada = "0000-00-00"
                
                print(f"[{contador_emails}/{len(ids_mensagens)}] Processando email: {assunto} ({data_formatada})")
                
                # Criar uma única pasta para todos os anexos deste email
                nome_pasta_email = re.sub(r'[\\/*?:"<>|]', '_', assunto)  # Remover caracteres inválidos
                nome_pasta_email = f"{data_formatada}_{nome_pasta_email}"
                
                # Adicionar um identificador único para evitar colisões
                id_mensagem_str = id_mensagem.decode('utf-8') if isinstance(id_mensagem, bytes) else str(id_mensagem)
                nome_pasta_email = f"{nome_pasta_email}_{id_mensagem_str}"
                
                # Criar pasta para este email (dentro da pasta da conta/empresa)
                pasta_destino_email = os.path.join(PASTA_DESTINO_BASE, nome_conta, nome_pasta_email)
                
                # Processar todos os anexos deste email para verificar se tem XML de interesse
                xmls_processados = []
                anexos_para_processar = []
                
                # Primeiro passo: Salvar todos os anexos em uma pasta temporária para analisar
                # ou analisar em memória. Vamos salvar primeiro para usar as funções existentes.
                temp_dir = os.path.join(PASTA_DESTINO_BASE, "temp_processamento")
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)
                
                for parte in mensagem.walk():
                    if parte.get_content_maintype() == 'multipart' or parte.get('Content-Disposition') is None:
                        continue
                    
                    nome_arquivo = parte.get_filename()
                    if nome_arquivo:
                        # Decodificar nome do arquivo
                        nome_decoded = decode_header(nome_arquivo)[0]
                        nome = nome_decoded[0]
                        encoding = nome_decoded[1]
                        if isinstance(nome, bytes):
                            nome = nome.decode(encoding if encoding else 'utf-8', errors='replace')
                        
                        nome_limpo = re.sub(r'[\\/*?:"<>|]', '_', nome)
                        caminho_temp = os.path.join(temp_dir, nome_limpo)
                        
                        with open(caminho_temp, 'wb') as f:
                            f.write(parte.get_payload(decode=True))
                        
                        anexos_para_processar.append((caminho_temp, nome_limpo))
                
                # Segundo passo: identificar XMLs e determinar se são de empresas AETE
                caminho_xml_principal = None
                for caminho_temp, nome_limpo in anexos_para_processar:
                    if nome_limpo.lower().endswith('.xml'):
                        # Tentar processar o XML
                        novo_caminho = processar_anexo_xml(caminho_temp, nome_limpo)
                        if novo_caminho and "NAO_PROCESSADOS" not in novo_caminho:
                            caminho_xml_principal = novo_caminho
                            xmls_processados.append(novo_caminho)
                            contador_anexos += 1
                
                # Terceiro passo: Se encontramos um XML válido, mover os outros anexos (PDFs) para a mesma pasta
                if caminho_xml_principal:
                    for caminho_temp, nome_limpo in anexos_para_processar:
                        if not nome_limpo.lower().endswith('.xml'):
                            processar_anexo_relacionado(caminho_temp, nome_limpo, caminho_xml_principal)
                            contador_anexos += 1
                    
                    # Salvar info do email na pasta do XML
                    pasta_final = os.path.dirname(caminho_xml_principal)
                    with open(os.path.join(pasta_final, "info_email.txt"), 'w', encoding='utf-8') as f:
                        f.write(f"Assunto: {assunto}\n")
                        f.write(f"Data: {data_formatada}\n")
                        f.write(f"De: {mensagem.get('From', 'Desconhecido')}\n")
                
                # Limpar arquivos temporários restantes
                for caminho_temp, _ in anexos_para_processar:
                    if os.path.exists(caminho_temp):
                        os.remove(caminho_temp)

            
            print(f"Processamento da conta {nome_conta} concluído: {contador_emails} emails encontrados, {contador_anexos} anexos salvos.")
            
            # Fechar conexão
            imap.close()
            imap.logout()
            
        except Exception as e:
            print(f"Erro durante o processamento da conta {nome_conta}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Remover pasta temporária se estiver vazia
    caminho_temp = os.path.join(PASTA_DESTINO_BASE, "temp")
    if os.path.exists(caminho_temp) and not os.listdir(caminho_temp):
        os.rmdir(caminho_temp)

def main():
    """Função principal do programa"""
    try:
        print("=== ROBÔ DE DOWNLOAD OUTLOOK (TUST AETE) ===")
        print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"Remetentes autorizados carregados: {len(REMETENTES_AUTORIZADOS)}")
        print(f"Transmissoras mapeadas: {len(TRANSMISSORAS)}")
        
        # Processar conta AETE
        baixar_anexos("AETE")
            
        print("\nProcesso concluído com sucesso!")
    except Exception as e:
        print(f"\nErro crítico durante o processo: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
