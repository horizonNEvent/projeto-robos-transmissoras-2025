import os
import requests
import re
import time
import json
import logging
import tempfile
import cv2
import traceback
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from paddleocr import PaddleOCR
from base_robot import BaseRobot

class LightRobot(BaseRobot):
    def __init__(self):
        super().__init__("light")
        self.base_url = "https://nfe.light.com.br"
        # OCR será inicializado sob demanda para evitar problemas de subprocesso
        # logging.getLogger("ppocr").setLevel(logging.ERROR) # Removido para teste
        
        self.session = requests.Session()
        self.session.verify = False
        requests.packages.urllib3.disable_warnings()
        
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

    def carregar_referencia_empresas_light(self):
        """Carrega Data/empresas.light.json"""
        try:
            # Caminho relativo considerando Robots/light.py -> ../Data/empresas.light.json
            json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Data', 'empresas.light.json')
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Erro ao carregar empresas.light.json: {e}")
            return {}

    def extrair_tokens_aspnet(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        viewstate = soup.find('input', {'name': '__VIEWSTATE'})
        eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})
        
        vs = viewstate.get('value', '') if viewstate else ''
        ev = eventvalidation.get('value', '') if eventvalidation else ''
        return vs, ev
    
    def _get_ocr_instance(self):
        """Retorna instância única do PaddleOCR otimizada para captchas simples."""
        if not hasattr(self, '_ocr_instance') or self._ocr_instance is None:
            self.logger.warning("⏳ Inicializando PaddleOCR (primeira vez = LENTA: 2-5 min, próximas = rápido)...")
            # Suprime logs verbosos via logging
            import logging as _logging
            for logger_name in ['ppocr', 'paddle', 'paddleocr', 'paddlex']:
                _logging.getLogger(logger_name).setLevel(_logging.ERROR)
            # Configuração mínima: sem modelos de layout/orientação pesados
            # Adequada para captchas simples (imagens pequenas, texto direto)
            try:
                self._ocr_instance = PaddleOCR(
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    lang='en'
                )
                self.logger.info("✓ PaddleOCR inicializado com sucesso!")
            except Exception as e:
                self.logger.error(f"Erro fatal ao inicializar PaddleOCR: {e}")
                raise
        return self._ocr_instance

    def processar_captcha(self, imagem_bytes):
        self.logger.info("Iniciando processamento de CAPTCHA...")
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp.write(imagem_bytes)
                tmp_path = tmp.name

            # Pré-processamento com OpenCV
            try:
                image = cv2.imread(tmp_path)
                image = cv2.resize(image, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                gray = clahe.apply(gray)
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
                
                processed_path = tmp_path.replace('.png', '_processed.png')
                cv2.imwrite(processed_path, binary_bgr)
            except Exception as cv_err:
                self.logger.error(f"Erro no OpenCV: {cv_err}")
                return None

            # Usa instância única do OCR
            ocr_local = self._get_ocr_instance()
            
            self.logger.info("Executando OCR...")
            resultado = ocr_local.predict(processed_path)
            
            texto = None
            
            # API predict() retorna list de OCRResult (cada um com rec_texts)
            try:
                itens = list(resultado) if not isinstance(resultado, list) else resultado
                # Log seguro: só extrai rec_texts sem converter arrays numpy
                textos_encontrados = []
                for item in itens:
                    if hasattr(item, 'rec_texts'):
                        textos_encontrados.extend(item.rec_texts or [])
                    elif isinstance(item, dict) and item.get('rec_texts'):
                        textos_encontrados.extend(item['rec_texts'])
                self.logger.info(f"OCR detectou {len(textos_encontrados)} texto(s): {textos_encontrados}")

                for item in itens:
                    # Formato novo: OCRResult com atributo rec_texts
                    if hasattr(item, 'rec_texts') and item.rec_texts:
                        texto = item.rec_texts[0]
                        break
                    # Formato dict-like
                    elif isinstance(item, dict) and item.get('rec_texts'):
                        texto = item['rec_texts'][0]
                        break
                    # Formato antigo: lista de listas [[bbox, (text, conf)], ...]
                    elif isinstance(item, list):
                        for line in item:
                            if isinstance(line, list) and len(line) >= 2:
                                txt_info = line[1]
                                if isinstance(txt_info, (tuple, list)) and txt_info:
                                    texto = txt_info[0]
                                    break
                        if texto:
                            break
            except Exception as parse_err:
                self.logger.error(f"Erro ao parsear resultado OCR: {parse_err}")
                import traceback; traceback.print_exc()

            # Limpeza
            try:
                os.unlink(tmp_path)
                if os.path.exists(processed_path): os.unlink(processed_path)
            except: pass
            
            if texto:
                final = ''.join(c for c in texto if c.isalnum()).lower()
                self.logger.info(f"Texto extraído: {final}")
                return final
                
            self.logger.warning("OCR não retornou texto válido.")
            return None
        except Exception as e:
            self.logger.error(f"Erro CRÍTICO no processar_captcha: {e}")
            traceback.print_exc()
            return None

    def fazer_login(self, cnpj, codigo_ons, tentativas=5):
        url_login = f"{self.base_url}/Web/wfmAutenticar.aspx"

        # Retry com backoff para timeout de conexão
        max_tentativas_conexao = 3
        for tentativa_conexao in range(1, max_tentativas_conexao + 1):
            try:
                resp = self.session.get(url_login, headers=self.headers, timeout=30)
                break
            except Exception as e:
                if tentativa_conexao < max_tentativas_conexao:
                    espera = 5 * tentativa_conexao  # 5s, 10s, 15s
                    self.logger.warning(f"Timeout conexão (tentativa {tentativa_conexao}/{max_tentativas_conexao}). Aguardando {espera}s...")
                    time.sleep(espera)
                else:
                    self.logger.error(f"Erro conexão inicial (após {max_tentativas_conexao} tentativas): {e}")
                    return False, None, None

        vs, ev = self.extrair_tokens_aspnet(resp.text)
        
        for tentativa in range(1, tentativas + 1):
            ts = int(time.time() * 1000)
            url_cap = f"{self.base_url}/Web/GenerateCaptcha.aspx?{ts}"
            try:
                r_cap = self.session.get(url_cap, headers=self.headers)
                captcha_code = self.processar_captcha(r_cap.content)
            except Exception as cap_err:
                self.logger.error(f"Erro ao processar captcha: {cap_err}")
                captcha_code = None
            
            # Se falhou OCR, tentar mais uma vez sem gastar tentativa de login
            if not captcha_code:
                self.logger.warning(f"Falha OCR Captcha (Tentativa {tentativa}/{tentativas})")
                time.sleep(1)
                continue

            self.logger.info(f"Tentando login (CAPTCHA: {captcha_code})")
            
            payload = {
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "__LASTFOCUS": "",
                "__VIEWSTATE": vs,
                "__EVENTVALIDATION": ev,
                "rblUsuario": "2",
                "tbxCnpj": cnpj,
                "tbxOns": codigo_ons,
                "tbxCodigoCaptcha": captcha_code,
                "btnAutenticar": "Autenticar"
            }
            
            r_auth = self.session.post(url_login, data=payload, headers=self.headers)
            
            # Redirecionamento 302 ou sucesso na URL
            if "wfmBuscaNotas.aspx" in r_auth.url:
                parsed = urllib.parse.urlparse(r_auth.url)
                params = urllib.parse.parse_qs(parsed.query)
                u = params.get('u', [None])[0]
                id_ = params.get('id', [None])[0]
                if u and id_:
                    self.logger.info(f"Login Sucesso! URL={r_auth.url}")
                    return True, u, id_
            
            # Tenta pegar erro
            soup = BeautifulSoup(r_auth.text, 'html.parser')
            err = soup.find('span', {'id': 'lblMensagem'})
            if err and err.text.strip():
                self.logger.warning(f"Erro login: {err.text.strip()}")
            
            # Atualiza tokens
            vs, ev = self.extrair_tokens_aspnet(r_auth.text)
            time.sleep(1.5)

        self.logger.error("Falha no login após todas tentativas")
        return False, None, None

    def buscar_notas(self, u, id_, ano, mes):
        url_busca = f"{self.base_url}/Web/wfmBuscaNotas.aspx"
        
        self.logger.info(f"4. Buscando notas do período {mes:02d}/{ano}...")
        
        # 1. GET Inicial na Busca (Igual script referência)
        params = {"u": u, "id": id_}
        
        headers_get = self.headers.copy()
        headers_get.update({
            "Referer": f"{self.base_url}/Web/wfmAutenticar.aspx",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1"
        })
        
        r_get = self.session.get(url_busca, params=params, headers=headers_get)
        
        vs, ev = self.extrair_tokens_aspnet(r_get.text)
        
        # ONS Value extraction
        soup = BeautifulSoup(r_get.text, 'html.parser')
        ons_val = "4313"
        ddl = soup.find('select', {'name': 'ddlONS'})
        if ddl:
            sel = ddl.find('option', {'selected': 'selected'})
            if sel: ons_val = sel.get('value', '4313')
            

        # 2. POST da Busca
        headers_post = self.headers.copy()
        headers_post.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.base_url,
            "Referer": f"{url_busca}?u={u}&id={id_}",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1"
        })

        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "__VIEWSTATE": vs,
            "__VIEWSTATEENCRYPTED": "",
            "__EVENTVALIDATION": ev,
            "ddlONS": ons_val,
            "ddlAno": str(ano),
            "ddlCompetencia": str(int(mes)), # Remove zero a esquerda se tiver
            "btnBuscar": "Buscar"
        }

        r_post = self.session.post(f"{url_busca}?u={u}&id={id_}", data=payload, headers=headers_post)
        
        soup = BeautifulSoup(r_post.text, 'html.parser')
        grid = soup.find('table', {'id': 'gvwResultado'})
        
        notas = []
        if grid:
            self.logger.info("Grid encontrado.")
            rows = grid.find_all('tr')[1:]
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 5:
                    link = cells[0].find('a')
                    if link:
                        href = link.get('href', '')
                        m = re.search(r"__doPostBack\('([^']*)'", href)
                        evt_target = m.group(1) if m else None
                        
                        if evt_target:
                            nota_info = {
                                'id': link.get('id', ''), # Extrai ID do elemento tbm
                                'eventtarget': evt_target,
                                'tipo': cells[2].text.strip(),
                                'nome_arquivo': cells[3].text.strip()
                            }
                            notas.append(nota_info)
        else:
            self.logger.info("Grid não encontrado na busca.")
            msg = soup.find('span', {'id': 'lblMensagem'})
            if msg: self.logger.warning(f"MSG SISTEMA: {msg.text.strip()}")

        return notas, r_post.text

    def baixar_arquivo(self, u, id_, nota_info, html_anterior, save_dir):
        url_busca = f"{self.base_url}/Web/wfmBuscaNotas.aspx"

        self.logger.info(f"Baixando {nota_info['tipo']}: {nota_info['nome_arquivo']}...")

        # Tokens do HTML da busca (que contém o resultado)
        vs, ev = self.extrair_tokens_aspnet(html_anterior)
        soup = BeautifulSoup(html_anterior, 'html.parser')

        def get_val(name, default):
            el = soup.find('select', {'name': name})
            if el:
                sel = el.find('option', {'selected': 'selected'})
                if sel: return sel.get('value', default)
            return default

        ons_val = get_val('ddlONS', '4313')
        ano_val = get_val('ddlAno', '2025')
        comp_val = get_val('ddlCompetencia', '8')

        headers_post = self.headers.copy()
        headers_post.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.base_url,
            "Referer": f"{url_busca}?u={u}&id={id_}",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1"
        })

        payload = {
            "__EVENTTARGET": nota_info['eventtarget'],
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "__VIEWSTATE": vs,
            "__VIEWSTATEENCRYPTED": "",
            "__EVENTVALIDATION": ev,
            "ddlONS": ons_val,
            "ddlAno": ano_val,
            "ddlCompetencia": comp_val
        }

        r_down = self.session.post(f"{url_busca}?u={u}&id={id_}", data=payload, headers=headers_post)

        self.logger.debug(f"Status Code: {r_down.status_code}, Content-Type: {r_down.headers.get('Content-Type', 'N/A')}")

        if r_down.status_code == 200:
            ctype = r_down.headers.get('Content-Type', '').lower()

            # Helper para detectar tipo real pelo conteudo
            content_start = r_down.content[:10]
            is_pdf = b'%PDF' in content_start
            is_xml = b'<?xml' in content_start or b'<nfeProc' in content_start
            is_html = b'<!DOCTYPE' in content_start or b'<html' in content_start

            # Log do que foi detectado
            self.logger.debug(f"Detecção: PDF={is_pdf}, XML={is_xml}, HTML={is_html}, Content-Type={ctype}")

            # Se for HTML, pode ser erro do servidor
            if is_html:
                self.logger.warning(f"Resposta é HTML (possível erro). Primeiras 500 chars: {r_down.text[:500]}")
                return False

            # Se for PDF/XML ou tiver header de arquivo, salva
            if is_pdf or is_xml or any(x in ctype for x in ['xml', 'pdf', 'octet-stream', 'application', 'image/jpeg']):
                filename = nota_info['nome_arquivo']
                cd = r_down.headers.get('Content-Disposition', '')
                if 'filename=' in cd:
                    m = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', cd)
                    if m: filename = m.group(1).strip('"\'')

                # Se detectou PDF mas a ext está errada, corrige
                if is_pdf and not filename.lower().endswith('.pdf'):
                    filename += '.pdf'
                if is_xml and not filename.lower().endswith('.xml'):
                    filename += '.xml'

                filename = re.sub(r'[\\/*?:"<>|]', "", filename)
                os.makedirs(save_dir, exist_ok=True)
                full_path = os.path.join(save_dir, filename)

                with open(full_path, 'wb') as f:
                    f.write(r_down.content)
                self.logger.info(f"Salvo: {filename} ({len(r_down.content)} bytes)")
                return True
            else:
                self.logger.warning(f"Tipo de arquivo desconhecido: {ctype}, Tamanho: {len(r_down.content)} bytes")
                return False
        else:
            self.logger.error(f"Erro no download: Status {r_down.status_code}. Headers: {dict(r_down.headers)}")
            return False

    def run(self):
        # Lógica de Competência
        if self.args.competencia:
            try:
                c = self.args.competencia.replace('/', '').replace('-', '')
                ano_busca = int(c[:4])
                mes_busca = int(c[4:6])
            except:
                self.logger.error("Competência inválida. Use YYYYMM.")
                return
        else:
            now = datetime.now()
            ano_busca = now.year
            mes_busca = now.month

        self.logger.info(f"Iniciando Light - Competência: {mes_busca:02d}/{ano_busca}")
        
        base_output_dir = self.get_output_path()

        # Tenta carregar config
        empresas = self.carregar_referencia_empresas_light()
        
        target_empresa = self.args.empresa # Esse "empresa" no front é o Grupo (AETE, DE, etc)
        target_agents = self.get_agents()
        # base_output_dir movido para cima
        
        # Argumento --user vindo do Front (Login/CNPJ Manual)
        cnpj_argumento = self.args.user

        # MODO DIRETO: Se temos CNPJ (--user) e ONS (--agente), processa direto sem ler JSON
        if self.args.user and self.args.agente:
            cnpj = self.args.user
            ons = str(self.args.agente)
            
            # Tenta pegar o nome da empresa via argumento --empresa, ou usa genérico
            nome_empresa = self.args.empresa or f"ONS_{ons}"
            
            self.logger.info(f"MODO DIRETO: Processando {nome_empresa} (ONS: {ons}) | CNPJ: {cnpj}")
            
            # Define diretório de saída
            # Padrão: downloads/TUST/LIGHT / NOME_EMPRESA / ONS
            save_dir = os.path.join(base_output_dir, nome_empresa, ons)
            
            self.session = requests.Session()
            self.session.verify = False

            ok, u, id_ = self.fazer_login(cnpj, ons)
            if ok:
                notas, html_busca = self.buscar_notas(u, id_, ano_busca, mes_busca)
                if notas:
                    self.logger.info(f"Encontradas {len(notas)} notas para {nome_empresa}.")
                    for nota in notas:
                        self.baixar_arquivo(u, id_, nota, html_busca, save_dir)
                else:
                    self.logger.info(f"Nenhuma nota encontrada para {nome_empresa}.")
            else:
                self.logger.error(f"Falha Login para {nome_empresa} (CNPJ: {cnpj}).")
            
            return # Encerra após processar o alvo direto

        # MODO VARREDURA (JSON): Se não foi passado user/agente específicos
        empresas = self.carregar_referencia_empresas_light()
        
        # Iterar sobre (Categoria -> Lista ou Dict)
        # Validação extra ANTES do loop
        if target_empresa and target_empresa.upper() != "LIGHT":
            found = any(g.upper() == target_empresa.upper() for g in empresas.keys())
            if not found:
                self.logger.error(f"A empresa '{target_empresa}' não foi encontrada em Data/empresas.light.json. Adicione os CNPJs neste arquivo.")
                return

        # Iterar sobre (Categoria -> Lista ou Dict)
        for grupo, itens in empresas.items():
            # Filtro de Grupo (AETE, DE, etc)
            if target_empresa and target_empresa.upper() not in [grupo.upper(), "LIGHT"]:
                continue

            # Unificar estrutura: Se for dict (ONS->Dados), transforma em lista para iterar igual
            if isinstance(itens, dict):
                lista_empresas = []
                for k, v in itens.items():
                    v['ons'] = k 
                    v['pasta'] = v['nome']
                    lista_empresas.append(v)
            else:
                lista_empresas = itens

            for idx, dados in enumerate(lista_empresas):
                ons = str(dados.get('ons') or dados.get('codigo_ons', ''))

                if target_agents and ons not in target_agents:
                    continue

                cnpj = dados.get('cnpj')
                nome_pasta = dados.get('pasta') or dados.get('nome') or f"ONS_{ons}"

                self.logger.info(f"Processando {grupo} - {nome_pasta} ({ons}) | CNPJ: {cnpj}")

                save_dir = os.path.join(base_output_dir, grupo, str(ons))

                self.session = requests.Session()
                self.session.verify = False

                ok, u, id_ = self.fazer_login(cnpj, ons)
                if ok:
                    notas, html_busca = self.buscar_notas(u, id_, ano_busca, mes_busca)
                    if notas:
                        self.logger.info(f"Encontradas {len(notas)} notas para {nome_pasta}.")
                        for nota in notas:
                            self.baixar_arquivo(u, id_, nota, html_busca, save_dir)
                    else:
                        self.logger.info(f"Nenhuma nota encontrada para {nome_pasta}.")
                else:
                    self.logger.error(f"Falha Login para {nome_pasta} (CNPJ: {cnpj}).")

                # Delay entre agentes para não sobrecarregar servidor
                if idx < len(lista_empresas) - 1:
                    time.sleep(3)

if __name__ == "__main__":
    bot = LightRobot()
    bot.run()
