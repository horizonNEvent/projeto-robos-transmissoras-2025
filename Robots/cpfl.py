import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

# Import BaseRobot
try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

class CPFLRobot(BaseRobot):
    """
    Robô para CPFL Transmissão (Versão Robustez do Usuário).
    """
    
    def __init__(self):
        super().__init__("cpfl")
        self.mapeamento = {}
        self.carregar_mapeamento()

    def carregar_mapeamento(self):
        try:
            p = Path(__file__).parent.parent / 'Data' / 'empresas_cpfl.json'
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.mapeamento = data.get("mapeamento_empresas", {})
        except: pass

    def get_fatura_name_for_agent(self, ons_code):
        ons_str = str(ons_code)
        found_name = None
        
        # 1. Try JSON first
        try:
            p = Path(__file__).parent.parent / 'Data' / 'empresas_cpfl.json'
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for empresa, agents in data.items():
                        if empresa == "mapeamento_empresas": continue
                        for a in agents:
                            if str(a.get("codigo")) == ons_str:
                                found_name = a.get("nome")
                                break
                        if found_name: break
        except: pass

        # 2. Try DB if not found in JSON
        if not found_name:
            try:
                import sqlite3
                db_path = Path(__file__).parent.parent / 'sql_app.db'
                if db_path.exists():
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    # Tenta na tabela empresas (campo nome_empresa)
                    cursor.execute("SELECT nome_empresa FROM empresas WHERE codigo_ons = ?", (ons_str,))
                    row = cursor.fetchone()
                    if row: found_name = row[0]
                    
                    if not found_name:
                        # Tenta na tabela transmissora (campo nome ou sigla)
                        cursor.execute("SELECT nome FROM transmissora WHERE codigo_ons = ?", (ons_str,))
                        row = cursor.fetchone()
                        if row: found_name = row[0]
                    conn.close()
            except: pass

        if found_name:
            return self.mapeamento.get(found_name, self.mapeamento.get("*", found_name))
            
        return self.mapeamento.get("*", "CEEE T")

    def monitor_respostas_403(self, page):
        state = {"had_403": False}
        def _on_response(response):
            try:
                if response.status == 403:
                    state["had_403"] = True
            except: pass
        page.on("response", _on_response)
        return state

    def pagina_interrompida(self, page):
        try:
            if page.locator("text=Network Connection Interrupted").count() > 0:
                return True
        except: pass
        return False

    def navegar_para_mes(self, page, data_site):
        """Localiza a pasta do mês/ano desejado e a expande usando JS Evaluate (Lógica Original Robusta)."""
        self.logger.info(f"Procurando nó do mês: {data_site}")
        
        try:
            # Aguarda o texto do mês aparecer
            selector = f"span.iceOutTxt:has-text('{data_site}')"
            page.wait_for_selector(selector, timeout=10000)
            
            data_element = page.locator(selector)
            
            if data_element.count() > 0:
                # Usa JS para achar o ID da linha pai (iceTreeRow)
                tree_node_id = data_element.first.evaluate("""el => {
                    const treeRow = el.closest('.iceTreeRow');
                    return treeRow ? treeRow.id : null;
                }""")
                
                if tree_node_id:
                    # Lógica do script original do usuário:
                    # Pega o ultimo numero apos o traco
                    # Ex: form:tree:n-0-0 -> 0
                    node_number = tree_node_id.split('-')[-1]
                    
                    self.logger.info(f"Nó número: {node_number} (ID Original: {tree_node_id})")
                    
                    # Constrói o seletor do botão de expandir
                    # Padrão IceFaces: #form:tree:<numero>
                    expand_selector = f"#form\\:tree\\:{node_number}"
                    
                    # Se não achar por esse, tenta o handle
                    handle_selector = f"#form\\:tree\\:{node_number}-handle"
                    
                    target_selector = None
                    if page.locator(expand_selector).count() > 0:
                        target_selector = expand_selector
                    elif page.locator(handle_selector).count() > 0:
                        target_selector = handle_selector
                        
                    if target_selector:
                        self.logger.info(f"Clicando para expandir: {target_selector}")
                        page.locator(target_selector).click()
                        time.sleep(3)
                        
                        # Sucesso, agora expande os filhos
                        self.expandir_subpastas(page, node_number)
                        return True
                    else:
                        # Ultima tentativa: Clicar no texto
                        self.logger.warning("Seletor de expansão não achado. Clicando no texto.")
                        data_element.first.click()
                        time.sleep(3)
                        self.expandir_subpastas(page, node_number)
                        return True
            return False
            
        except Exception as e:
            self.logger.error(f"Erro ao navegar para mês: {e}")
            return False

    def expandir_subpastas(self, page, node_number):
        """Expande todos os agentes dentro do mês para revelar as faturas"""
        try:
            time.sleep(2)
            # Div container dos filhos
            # O ID container costuma ser form:tree-d-<numero>
            # Vamos tentar iterar cegamente nos filhos diretos possíveis (0 a 10)
            
            self.logger.info(f"Tentando expandir sub-itens de {node_number}...")
            
            for i in range(20): # Tenta até 20 sub-agentes
                try:
                    # O handle de expansão do filho i
                    # ID provavel: form:tree:<node_number>-<i>-handle
                    sub_handle = f"#form\\:tree\\:{node_number}-{i}-handle"
                    
                    if page.locator(sub_handle).is_visible():
                        self.logger.info(f"Expandindo Agente {i}...")
                        page.locator(sub_handle).click()
                        time.sleep(1.5)
                    else:
                        # Se não achou handle visivel para o indice i, pode ser que acabou ou o ID é diferente
                        # Vamos tentar clicar no link do texto se o handle nao existir
                        # ID do link texto: form:tree:<node_number>-<i>
                        sub_link = f"#form\\:tree\\:{node_number}-{i}"
                        if page.locator(sub_link).is_visible():
                             self.logger.info(f"Expandindo Agente {i} (via texto)...")
                             page.locator(sub_link).click()
                             time.sleep(1.5)
                except: pass
                
        except Exception as e:
            self.logger.error(f"Erro na expansão: {e}")

    def baixar_documentos(self, page, ons_code, output_dir):
        # Pausa crucial para garantir que a expansão terminou de renderizar os textos
        time.sleep(3)
        
        # Nome da fatura esperado no mapeamento
        nome_fatura = self.get_fatura_name_for_agent(ons_code)
        selector = f"text={nome_fatura} - Fatura" if nome_fatura else "text= - Fatura"
        
        self.logger.info(f"Buscando faturas: '{selector}'")
        faturas = page.locator(selector)
        count = faturas.count()
        self.logger.info(f"Encontradas {count} faturas.")

        for i in range(count):
            try:
                fatura_item = faturas.nth(i)
                txt = fatura_item.inner_text()
                
                # Extração do número da NF para nomear arquivos/pastas
                try:
                    num = txt.split('Nº: ')[1].split(' -')[0].strip().replace('.','').replace('/','').replace('-','')
                except: num = f"UNK_{i}"
                
                # Pasta Final
                final_path = os.path.join(output_dir, f"NF_{num}")
                os.makedirs(final_path, exist_ok=True)
                
                # O FLUXO SECRETO: Clicar no TreeNode via ID padronizado para ativar a seleção correta
                fatura_selector = f'span[class="iceOutTxt"][id="form:tree:n-0-{i}:TreeNode"]'
                try:
                    page.click(fatura_selector, timeout=5000)
                    self.logger.info(f"Clicou no TreeNode {i}. Aguardando ícones...")
                except:
                    fatura_item.click()
                
                time.sleep(2)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # PDF - Busca o último ícone que apareceu para garantir que é o do nó ativado
                try:
                    pdf_ico = page.locator('img[src*="pdf_ico.png"]').last
                    if pdf_ico.is_visible(timeout=5000):
                        with page.expect_download() as dl_info:
                            pdf_ico.click()
                            dl = dl_info.value
                            dl.save_as(os.path.join(final_path, f"DANFE_CPFL_{num}_{ts}.pdf"))
                        self.logger.info(f"PDF Baixado: {num}")
                except: pass
                
                # XML - Clica no link específico (nth) para abrir a seção do XML
                try:
                    nf_link = page.locator('text=Nota Fiscal Modelo').nth(i)
                    if nf_link.is_visible(timeout=3000):
                        nf_link.click()
                        time.sleep(1)
                        # Busca o último ícone de XML que apareceu
                        xml_ico = page.locator('img[src*="xml"]').last
                        if xml_ico.is_visible(timeout=5000):
                            with page.expect_download() as dl_info:
                                xml_ico.click()
                                dl = dl_info.value
                                dl.save_as(os.path.join(final_path, f"NFe_CPFL_{num}_{ts}.xml"))
                            self.logger.info(f"XML Baixado: {num}") 
                except: pass
                
            except Exception as e:
                self.logger.error(f"Erro no item {i}: {e}")

    def lookup_cnpj(self, ons_code):
        """Busca o CNPJ para um código ONS em diversos locais (JSONs e Banco)."""
        ons_str = str(ons_code)
        
        # 1. CPFL Specific JSON
        try:
            p = Path(__file__).parent.parent / 'Data' / 'empresas_cpfl.json'
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if k == "mapeamento_empresas": continue
                        for a in v:
                            if str(a.get("codigo")) == ons_str and a.get("cnpj"):
                                return a.get("cnpj")
        except: pass

        # 2. General TUST JSON (Onde costumam estar os da RE)
        try:
            p = Path(__file__).parent.parent / 'Email' / 'tust.json'
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        if str(item.get("ONS")) == ons_str:
                            return item.get("CNPJ")
        except: pass

        # 3. Direct DB Check (Busca literal no banco de dados sql_app.db)
        try:
            import sqlite3
            # O banco oficial agora é sql_app.db na raiz
            db_path = Path(__file__).parent.parent / 'sql_app.db'
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # Tenta na tabela 'empresas' (Padrão para AE/DE/AETE)
                cursor.execute("SELECT cnpj FROM empresas WHERE codigo_ons = ?", (ons_str,))
                row = cursor.fetchone()
                if row and row[0]:
                    conn.close()
                    return row[0]
                
                # Tenta na tabela 'transmissora' (Backup)
                cursor.execute("SELECT cnpj FROM transmissora WHERE codigo_ons = ?", (ons_str,))
                row = cursor.fetchone()
                conn.close()
                if row and row[0]: return row[0]
        except Exception as e:
            self.logger.error(f"Erro ao consultar banco p/ CNPJ: {e}")
        
        return None

    def process_agent(self, cnpj, senha, ons, data_site, out_dir):
        """Executa o download para um único agente/CNPJ."""
        max_retries = 2
        for attempt in range(max_retries + 1):
            if attempt > 0: self.logger.info(f"Tentativa {attempt+1} para {ons}...")
            
            with sync_playwright() as p:
                # Mudamos para Chromium e desativamos flags de automação
                browser = p.chromium.launch(
                    headless=self.args.headless, 
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--start-maximized"
                    ],
                    slow_mo=1000 # 1 segundo entre ações para ser super conservador
                )
                
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                
                context = browser.new_context(
                    accept_downloads=True,
                    user_agent=user_agent,
                    viewport=None # Usa o tamanho nativo do browser maximizado
                )
                page = context.new_page()
                
                # Script extra para remover o rastro de "WebDriver"
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                state_403 = self.monitor_respostas_403(page)
                
                try:
                    import random
                    self.logger.info(f"Acessando CPFL p/ Agente {ons} (Login CNPJ: {cnpj})...")
                    time.sleep(random.uniform(3, 6)) # Espera aleatória entre 3 e 6 segundos
                    page.goto('https://getweb.cpfl.com.br/getweb/getweb.jsf', timeout=90000, wait_until="domcontentloaded")
                    
                    # Login
                    if page.locator('#form\\:documento').is_visible():
                        page.fill('#form\\:documento', cnpj)
                        page.fill('#form\\:senha', senha)
                        page.click('#form\\:j_idt22')
                    
                    # Wait Arvore
                    try:
                        page.wait_for_selector('.iceTree', timeout=30000)
                    except:
                        if "inválido" in page.content().lower():
                            self.logger.error(f"Credenciais inválidas para CNPJ {cnpj}.")
                            return False
                        raise Exception("Timeout login")

                    if self.pagina_interrompida(page) or state_403['had_403']:
                        raise Exception("Conexão interrompida/403")

                    # Navegação
                    success = self.navegar_para_mes(page, data_site)
                    if not success:
                        self.logger.error(f"Mês {data_site} não encontrado para {ons}.")
                        return False

                    # Download
                    self.baixar_documentos(page, ons, out_dir)
                    return True # Sucesso

                except Exception as e:
                    self.logger.error(f"Erro no agente {ons}: {e}")
                    if attempt == max_retries:
                        self.logger.error(f"Max tentativas excedido para {ons}.")
                    time.sleep(5)
                finally:
                    browser.close()
        return False

    def run(self):
        # 1. Recupera Lista de Agentes vinculados
        agents = self.get_agents()
        if not agents:
            self.logger.error("Nenhum agente fornecido via --agente.")
            return

        # 2. Argumentos Globais
        global_cnpj = self.args.user
        senha = self.args.password
        
        # 3. Competencia
        if self.args.competencia:
            c = self.args.competencia
            try:
                mes = int(c[4:6])
                ano = int(c[:4])
            except: 
                self.logger.error("Data invalida")
                return
        else:
            now = datetime.now()
            if now.month == 1:
                mes, ano = 12, now.year - 1
            else:
                mes, ano = now.month - 1, now.year
        
        data_site = f"{mes:02d}/{ano}"
        
        # 4. Pasta de Saída Base
        base_out_dir = self.get_output_path()

        # 5. Iteração sobre Agentes
        for ons in agents:
            self.logger.info(f"--- AGENTE: {ons} ---")
            
            # Determina o CNPJ (Login)
            cnpj = global_cnpj
            if not cnpj:
                cnpj = self.lookup_cnpj(ons)
            
            if not cnpj:
                self.logger.warning(f"CNPJ não encontrado p/ agente {ons}. Usando o código ONS como login.")
                cnpj = ons
            
            # Subpasta para este agente
            agent_out_dir = os.path.join(base_out_dir, ons)
            
            # Executa o login e download
            self.process_agent(cnpj, senha, ons, data_site, agent_out_dir)


if __name__ == "__main__":
    robot = CPFLRobot()
    robot.run()
