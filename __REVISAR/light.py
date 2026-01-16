#!/usr/bin/env python3
"""
Script para baixar notas da Light usando requests para todas as empresas
"""

import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import unquote, quote
import json
from paddleocr import PaddleOCR
import cv2
import numpy as np
import os
import tempfile
from datetime import datetime

class LightRequestsTest:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://nfe.light.com.br"
        # Usar parâmetros atualizados do PaddleOCR
        self.ocr = PaddleOCR(use_textline_orientation=True, lang='en')
        
        # Headers padrão
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1"
        }
        
        # Desabilitar verificação SSL (apenas para teste)
        self.session.verify = False
        requests.packages.urllib3.disable_warnings()
        
    def extrair_tokens_aspnet(self, html):
        """Extrai VIEWSTATE e EVENTVALIDATION do HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        
        viewstate = ""
        eventvalidation = ""
        
        # Procurar __VIEWSTATE
        viewstate_input = soup.find('input', {'name': '__VIEWSTATE'})
        if viewstate_input:
            viewstate = viewstate_input.get('value', '')
            
        # Procurar __EVENTVALIDATION
        eventvalidation_input = soup.find('input', {'name': '__EVENTVALIDATION'})
        if eventvalidation_input:
            eventvalidation = eventvalidation_input.get('value', '')
            
        return viewstate, eventvalidation
    
    def processar_captcha(self, imagem_bytes):
        """Processa o CAPTCHA usando PaddleOCR"""
        try:
            # Salvar temporariamente para processar
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp.write(imagem_bytes)
                tmp_path = tmp.name
            
            # Ler imagem original
            image = cv2.imread(tmp_path)
            
            # Redimensionar para facilitar OCR
            image = cv2.resize(image, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            
            # OCR usando o caminho do arquivo ao invés da matriz numpy
            resultado = self.ocr.ocr(tmp_path)
            
            # Debug da estrutura
            print(f"Tipo do resultado OCR: {type(resultado)}")
            if resultado:
                print(f"Estrutura completa: {resultado}")
                if len(resultado) > 0 and resultado[0]:
                    print(f"Primeiro elemento: {resultado[0]}")
            
            # Tentar extrair texto de diferentes estruturas possíveis
            texto = None
            
            if resultado and len(resultado) > 0:
                # Nova estrutura do PaddleOCR - retorna um dicionário
                if isinstance(resultado[0], dict):
                    # O texto reconhecido está em 'rec_texts'
                    if 'rec_texts' in resultado[0] and resultado[0]['rec_texts']:
                        texto = resultado[0]['rec_texts'][0]  # Pegar o primeiro texto reconhecido
                        score = resultado[0].get('rec_scores', [0])[0] if 'rec_scores' in resultado[0] else 0
                        print(f"Texto extraído do dicionário: '{texto}' (confiança: {score:.2%})")
                # Estrutura antiga - lista de listas
                elif isinstance(resultado[0], list) and len(resultado[0]) > 0:
                    for item in resultado[0]:
                        if isinstance(item, list) and len(item) >= 2:
                            # item[1] geralmente contém (texto, confiança)
                            if isinstance(item[1], tuple) and len(item[1]) >= 1:
                                texto = item[1][0]
                                print(f"Texto extraído (estrutura tuple): {texto}")
                                break
                            elif isinstance(item[1], str):
                                texto = item[1]
                                print(f"Texto extraído (estrutura string): {texto}")
                                break
            
            # Limpar arquivo temporário
            try:
                os.unlink(tmp_path)
            except:
                pass
            
            if texto:
                # Limpar o texto - remover espaços e caracteres especiais
                texto_limpo = ''.join(c for c in texto if c.isalnum()).lower()
                print(f"CAPTCHA reconhecido e limpo: {texto_limpo}")
                return texto_limpo
            else:
                print("Não foi possível reconhecer o CAPTCHA")
                return None
                
        except Exception as e:
            print(f"Erro ao processar CAPTCHA: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def fazer_login(self, cnpj, codigo_ons, tentativas: int = 3, pausa_seg: float = 1.5):
        """Realiza o processo completo de login com tentativas automáticas de CAPTCHA.

        tentativas: número de tentativas de reconhecimento/validação do CAPTCHA
        pausa_seg: pausa entre tentativas para evitar bloqueios
        """

        print("=" * 50)
        print(f"Iniciando login para CNPJ: {cnpj}, ONS: {codigo_ons}")
        print("=" * 50)

        url_login = f"{self.base_url}/Web/wfmAutenticar.aspx"

        headers_get = self.headers.copy()
        headers_get.update({
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none"
        })

        # GET inicial para obter sessão e tokens
        print("\n1. Fazendo GET inicial...")
        response = self.session.get(url_login, headers=headers_get)
        print(f"Status: {response.status_code}")
        print(f"Cookies recebidos: {self.session.cookies.get_dict()}")

        viewstate, eventvalidation = self.extrair_tokens_aspnet(response.text)
        print(f"\nVIEWSTATE encontrado: {viewstate[:50]}..." if viewstate else "VIEWSTATE não encontrado!")
        print(f"EVENTVALIDATION encontrado: {eventvalidation[:50]}..." if eventvalidation else "EVENTVALIDATION não encontrado!")

        headers_captcha = self.headers.copy()
        headers_captcha.update({
            "Referer": url_login,
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "same-origin"
        })

        headers_post = self.headers.copy()
        headers_post.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.base_url,
            "Referer": url_login,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1"
        })

        # Loop de tentativas
        for tentativa in range(1, tentativas + 1):
            print(f"\n2. Baixando CAPTCHA... (tentativa {tentativa}/{tentativas})")
            timestamp = int(time.time() * 1000)
            url_captcha = f"{self.base_url}/Web/GenerateCaptcha.aspx?{timestamp}"

            response_captcha = self.session.get(url_captcha, headers=headers_captcha)
            print(f"Status CAPTCHA: {response_captcha.status_code}")
            print(f"Tamanho da imagem: {len(response_captcha.content)} bytes")

            codigo_captcha = self.processar_captcha(response_captcha.content)
            if not codigo_captcha:
                print("Não foi possível reconhecer o CAPTCHA automaticamente.")
                if tentativa < tentativas:
                    time.sleep(pausa_seg)
                    # Tentar novamente com novo CAPTCHA
                    continue

            print(f"\n3. Fazendo POST de autenticação com CAPTCHA: {codigo_captcha}")

            form_data = {
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "__LASTFOCUS": "",
                "__VIEWSTATE": viewstate,
                "__EVENTVALIDATION": eventvalidation,
                "rblUsuario": "2",  # 2 = Fornecedor
                "tbxCnpj": cnpj,
                "tbxOns": codigo_ons,
                "tbxCodigoCaptcha": codigo_captcha or "",
                "btnAutenticar": "Autenticar"
            }

            response_auth = self.session.post(url_login, data=form_data, headers=headers_post)
            print(f"Status POST: {response_auth.status_code}")

            # Sucesso: redirecionado para busca de notas
            if "wfmBuscaNotas.aspx" in response_auth.url:
                print("\n✓ LOGIN REALIZADO COM SUCESSO!")
                print(f"Redirecionado para: {response_auth.url}")

                import urllib.parse
                parsed = urllib.parse.urlparse(response_auth.url)
                params = urllib.parse.parse_qs(parsed.query)

                if 'u' in params and 'id' in params:
                    print(f"Parâmetro u: {params['u'][0]}")
                    print(f"Parâmetro id: {params['id'][0]}")
                    return True, params['u'][0], params['id'][0]
                else:
                    print("Parâmetros u e id não encontrados na URL")
                    return True, None, None

            # Falha: verificar mensagem e decidir se tenta novamente
            print("\n✗ FALHA NO LOGIN")
            soup = BeautifulSoup(response_auth.text, 'html.parser')
            erro = soup.find('span', {'id': 'lblMensagem'})
            msg_text = erro.text.strip() if erro else ""
            if msg_text:
                print(f"Mensagem de erro: {msg_text}")

            # Se a mensagem indicar erro de CAPTCHA, tentar novamente até o limite
            if any(x in msg_text.lower() for x in ["código de segurança", "captcha", "segurança não confere"]):
                if tentativa < tentativas:
                    print("Tentando novamente com um novo CAPTCHA...")
                    time.sleep(pausa_seg)
                    continue

            # Outros erros: interrompe
            break

        # Se chegou aqui, todas as tentativas falharam
        return False, None, None
    
    def buscar_notas_por_periodo(self, u_param, id_param, ano, mes):
        """Busca as notas de um período específico"""
        print(f"\n4. Buscando notas do período {mes:02d}/{ano}...")
        
        url_busca = f"{self.base_url}/Web/wfmBuscaNotas.aspx"
        
        # Primeiro GET para obter a página e tokens
        params = {
            "u": u_param,
            "id": id_param
        }
        
        headers_get = self.headers.copy()
        headers_get.update({
            "Referer": f"{self.base_url}/Web/wfmAutenticar.aspx",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1"
        })
        
        response = self.session.get(url_busca, params=params, headers=headers_get)
        print(f"Status GET inicial: {response.status_code}")
        
        # Extrair tokens para o POST
        viewstate, eventvalidation = self.extrair_tokens_aspnet(response.text)
        
        # Extrair o ddlONS selecionado
        soup = BeautifulSoup(response.text, 'html.parser')
        ddl_ons = soup.find('select', {'name': 'ddlONS'})
        ons_value = "4313"  # Valor padrão
        if ddl_ons:
            selected_option = ddl_ons.find('option', {'selected': 'selected'})
            if selected_option:
                ons_value = selected_option.get('value', '4313')
        
        print(f"ONS selecionado: {ons_value}")
        
        # POST para buscar notas do período
        headers_post = self.headers.copy()
        headers_post.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.base_url,
            "Referer": f"{url_busca}?u={u_param}&id={id_param}",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1"
        })
        
        form_data = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEENCRYPTED": "",
            "__EVENTVALIDATION": eventvalidation,
            "ddlONS": ons_value,
            "ddlAno": str(ano),
            "ddlCompetencia": str(mes),
            "btnBuscar": "Buscar"
        }
        
        response_busca = self.session.post(f"{url_busca}?u={u_param}&id={id_param}", 
                                          data=form_data, 
                                          headers=headers_post)
        
        print(f"Status POST busca: {response_busca.status_code}")
        
        # Analisar resultados
        soup = BeautifulSoup(response_busca.text, 'html.parser')
        
        # Procurar pela grid de resultados
        grid = soup.find('table', {'id': re.compile(r'gvwResultado|gvResultado|gridResultado', re.I)})
        
        if grid:
            print("\n✓ Tabela de resultados encontrada!")
            
            # Procurar todas as linhas da tabela
            rows = grid.find_all('tr')[1:]  # Pular o header
            notas_encontradas = []
            
            for idx, row in enumerate(rows):
                cells = row.find_all('td')
                if cells and len(cells) >= 5:
                    # Extrair informações da linha
                    link = cells[0].find('a')
                    if link:
                        # Extrair o __doPostBack do href
                        href = link.get('href', '')
                        # O formato é: javascript:__doPostBack('gvwResultado$ctl02$lbnNota','')
                        match = re.search(r"__doPostBack\('([^']+)'", href)
                        eventtarget = match.group(1) if match else None
                        
                        nota_info = {
                            'id': link.get('id', ''),
                            'eventtarget': eventtarget,  # Usar este para o download
                            'data_emissao': cells[1].text.strip(),
                            'tipo': cells[2].text.strip(),
                            'nome_arquivo': cells[3].text.strip(),
                            'num_doc': cells[4].text.strip(),
                            'href': href
                        }
                        notas_encontradas.append(nota_info)
                        print(f"  - {nota_info['tipo']}: {nota_info['nome_arquivo']} ({nota_info['data_emissao']})")
            
            return response_busca.text, notas_encontradas
        else:
            print("✗ Nenhuma tabela de resultados encontrada")
            
            # Verificar se há mensagem de erro
            msg = soup.find('span', {'id': 'lblMensagem'})
            if msg:
                print(f"Mensagem do sistema: {msg.text}")
            
            return response_busca.text, []
    
    def baixar_xml_nota(self, u_param, id_param, nota_info, html_busca, pasta_empresa):
        """Baixa o XML de uma nota específica"""
        print(f"\n5. Baixando {nota_info['tipo']}: {nota_info['nome_arquivo']}...")
        
        url_busca = f"{self.base_url}/Web/wfmBuscaNotas.aspx"
        
        # Extrair tokens do HTML da busca
        viewstate, eventvalidation = self.extrair_tokens_aspnet(html_busca)
        
        # Extrair valores do formulário
        soup = BeautifulSoup(html_busca, 'html.parser')
        
        # Pegar valores dos dropdowns
        ddl_ons = soup.find('select', {'name': 'ddlONS'})
        ons_value = "4313"
        if ddl_ons:
            selected = ddl_ons.find('option', {'selected': 'selected'})
            if selected:
                ons_value = selected.get('value', '4313')
        
        ddl_ano = soup.find('select', {'name': 'ddlAno'})
        ano_value = "2025"
        if ddl_ano:
            selected = ddl_ano.find('option', {'selected': 'selected'})
            if selected:
                ano_value = selected.get('value', '2025')
        
        ddl_comp = soup.find('select', {'name': 'ddlCompetencia'})
        comp_value = "8"  # Valor padrão agosto
        if ddl_comp:
            selected = ddl_comp.find('option', {'selected': 'selected'})
            if selected:
                comp_value = selected.get('value', '8')
        
        # POST para baixar o arquivo
        headers_post = self.headers.copy()
        headers_post.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.base_url,
            "Referer": f"{url_busca}?u={u_param}&id={id_param}",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1"
        })
        
        # Usar o eventtarget correto (formato: gvwResultado$ctl02$lbnNota)
        form_data = {
            "__EVENTTARGET": nota_info['eventtarget'],  # Usar o formato correto
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEENCRYPTED": "",
            "__EVENTVALIDATION": eventvalidation,
            "ddlONS": ons_value,
            "ddlAno": ano_value,
            "ddlCompetencia": comp_value
        }
        
        print(f"  __EVENTTARGET: {nota_info['eventtarget']}")
        
        response_download = self.session.post(f"{url_busca}?u={u_param}&id={id_param}", 
                                             data=form_data, 
                                             headers=headers_post)
        
        print(f"Status download: {response_download.status_code}")
        
        # Verificar o tipo de conteúdo
        content_type = response_download.headers.get('Content-Type', '')
        print(f"Content-Type: {content_type}")
        
        # Determinar se é um arquivo binário baseado no tipo
        is_file = False
        if any(x in content_type.lower() for x in ['xml', 'pdf', 'octet-stream', 'application/pdf']):
            is_file = True
        
        # Também verificar se o conteúdo não é HTML
        if not is_file and response_download.content:
            # Verificar se não é HTML
            content_start = response_download.content[:500]
            if b'<!DOCTYPE' not in content_start and b'<html' not in content_start:
                is_file = True
        
        if is_file:
            # É um arquivo (XML, PDF ou Boleto)
            filename = nota_info['nome_arquivo']
            
            # Tentar extrair o nome do arquivo do header se disponível
            content_disp = response_download.headers.get('Content-Disposition', '')
            if 'filename=' in content_disp:
                match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disp)
                if match:
                    filename = match.group(1).strip('"\'')
            
            # Criar pasta da empresa se não existir
            os.makedirs(pasta_empresa, exist_ok=True)
            
            # Caminho completo do arquivo
            caminho_arquivo = os.path.join(pasta_empresa, filename)
            
            # Salvar o arquivo
            with open(caminho_arquivo, 'wb') as f:
                f.write(response_download.content)
            
            print(f"✓ Arquivo salvo como: {caminho_arquivo}")
            print(f"  Tamanho: {len(response_download.content)} bytes")
            print(f"  Tipo: {nota_info['tipo']}")
            
            return True, caminho_arquivo
        else:
            # Não é um arquivo, provavelmente é HTML com erro
            print("✗ Resposta não é um arquivo (recebido HTML)")
            
            # Verificar mensagem de erro
            soup = BeautifulSoup(response_download.text, 'html.parser')
            msg = soup.find('span', {'id': 'lblMensagem'})
            if msg and msg.text.strip():
                print(f"Mensagem: {msg.text}")
            
            return False, None

    def processar_empresa(self, cnpj, ons, nome_ons, grupo, ano, mes):
        """Processa uma empresa específica"""
        print(f"\n{'='*80}")
        print(f"PROCESSANDO: {grupo} - {nome_ons} (ONS: {ons})")
        print(f"CNPJ: {cnpj}")
        print(f"{'='*80}")
        
        # Criar pasta base para downloads
        # Padronizando igual aos outros robôs: LIGHT / Grupo / Código ONS
        base_dir = r"C:\Users\Bruno\Downloads\TUST\LIGHT"
        pasta_base = os.path.join(base_dir, grupo, ons)
        os.makedirs(pasta_base, exist_ok=True)
        
        # Tentar fazer login
        sucesso, u_param, id_param = self.fazer_login(cnpj, ons)
        
        if sucesso and u_param and id_param:
            # Se login bem-sucedido, buscar notas do período
            html_resultado, notas = self.buscar_notas_por_periodo(u_param, id_param, ano, mes)
            
            if notas:
                print(f"\n✓ Encontradas {len(notas)} arquivo(s) para {nome_ons}")
                
                # Baixar todos os arquivos
                arquivos_baixados = []
                for nota in notas:
                    sucesso_download, arquivo = self.baixar_xml_nota(
                        u_param, 
                        id_param, 
                        nota,
                        html_resultado,
                        pasta_base
                    )
                    
                    if sucesso_download:
                        arquivos_baixados.append(arquivo)
                        print(f"  ✓ Salvo: {arquivo}")
                    else:
                        print(f"  ✗ Falha ao baixar: {nota['nome_arquivo']}")
                
                print(f"\n✓ {nome_ons}: {len(arquivos_baixados)} arquivo(s) baixado(s) com sucesso")
                return True, len(arquivos_baixados)
            else:
                print(f"\n✗ {nome_ons}: Nenhuma nota encontrada para o período")
                return False, 0
        else:
            print(f"\n✗ {nome_ons}: Falha no login")
            return False, 0


def main():
    """Função principal para processar todas as empresas"""
    
    # Período para buscar (mês e ano atual)
    hoje = datetime.now()
    ANO_BUSCA = hoje.year
    MES_BUSCA = hoje.month
    
    print("=" * 80)
    print("SISTEMA DE DOWNLOAD AUTOMÁTICO - LIGHT")
    print(f"Período: {MES_BUSCA:02d}/{ANO_BUSCA}")
    print("=" * 80)
    
    # Carregar configuração das empresas
    try:
        # Caminho igual ao da assu
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'Data', 'empresas.light.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            empresas_config = json.load(f)
    except FileNotFoundError:
        print(f"ERRO: Arquivo {config_path} não encontrado!")
        return
    except Exception as e:
        print(f"ERRO ao carregar configuração: {e}")
        return
    
    # Criar instância do processador
    processor = LightRequestsTest()
    
    # Contadores
    total_empresas = 0
    empresas_sucesso = 0
    total_arquivos = 0
    
    # Processar todas as categorias/grupos de empresas
    for grupo, mapping in empresas_config.items():
        print(f"\n{'='*60}")
        print(f"GRUPO: {grupo} ({len(mapping)} empresas)")
        print(f"{'='*60}")

        for ons, dados in mapping.items():
            total_empresas += 1
            cnpj = dados['cnpj']
            nome_ons = dados['nome']

            try:
                sucesso, qtd_arquivos = processor.processar_empresa(cnpj, ons, nome_ons, grupo, ANO_BUSCA, MES_BUSCA)

                if sucesso:
                    empresas_sucesso += 1
                    total_arquivos += qtd_arquivos

                # Pausa entre empresas para evitar sobrecarga
                time.sleep(2)

            except Exception as e:
                print(f"ERRO ao processar {nome_ons} (ONS: {ons}): {e}")
                continue
    
    # Relatório final
    print(f"\n{'='*80}")
    print("RELATÓRIO FINAL")
    print(f"{'='*80}")
    print(f"Total de empresas processadas: {total_empresas}")
    print(f"Empresas com sucesso: {empresas_sucesso}")
    print(f"Empresas com falha: {total_empresas - empresas_sucesso}")
    print(f"Total de arquivos baixados: {total_arquivos}")
    print(f"Período processado: {MES_BUSCA:02d}/{ANO_BUSCA}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()