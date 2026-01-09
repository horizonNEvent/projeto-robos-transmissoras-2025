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
        try:
            p = Path(__file__).parent.parent / 'Data' / 'empresas_cpfl.json'
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    found_name = None
                    for empresa, agents in data.items():
                        if empresa == "mapeamento_empresas": continue
                        for a in agents:
                            if str(a.get("codigo")) == str(ons_code):
                                found_name = a.get("nome")
                                break
                        if found_name: break
                    if found_name:
                        return self.mapeamento.get(found_name, self.mapeamento.get("*", found_name))
        except: pass
        return self.mapeamento.get("*", "")

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
        
        # Nome da fatura esperado
        nome_fatura = self.get_fatura_name_for_agent(ons_code)
        selector = f"text={nome_fatura} - Fatura" if nome_fatura else "text= - Fatura"
        
        self.logger.info(f"Buscando faturas visíveis: '{selector}'")
        faturas = page.locator(selector)
        count = faturas.count()
        self.logger.info(f"Encontrados: {count}")

        for i in range(count):
            try:
                fatura_item = faturas.nth(i)
                txt = fatura_item.inner_text()
                
                # Numero
                try:
                    num = txt.split('Nº: ')[1].split(' -')[0].strip().replace('.','').replace('/','').replace('-','')
                except: num = f"UNK_{i}"
                
                # Pasta Final
                final_path = os.path.join(output_dir, f"NF_{num}")
                os.makedirs(final_path, exist_ok=True)
                
                # Clica na Fatura para ver os icones
                fatura_item.click()
                time.sleep(2)
                
                ts = datetime.now().strftime("%Y%m%d")
                
                # PDF
                try:
                    pdf_ico = page.locator('img[src*="pdf_ico.png"]').last
                    if pdf_ico.is_visible(timeout=3000):
                        with page.expect_download() as dl_info:
                            pdf_ico.click()
                            dl = dl_info.value
                            dl.save_as(os.path.join(final_path, f"DANFE_CPFL_{num}_{ts}.pdf"))
                        self.logger.info(f"PDF Baixado: {num}")
                except: pass
                
                # XML
                try:
                    # Precisa clicar em "Nota Fiscal Modelo" para ver o XML?
                    nf_link = page.locator('text=Nota Fiscal Modelo').last # Pega o ultimo visivel (do item atual expandido)
                    if nf_link.is_visible():
                        nf_link.click()
                        time.sleep(1)
                        xml_ico = page.locator('img[src*="xml"]').last
                        if xml_ico.is_visible(timeout=3000):
                            with page.expect_download() as dl_info:
                                xml_ico.click()
                                dl = dl_info.value
                                dl.save_as(os.path.join(final_path, f"NFe_CPFL_{num}_{ts}.xml"))
                            self.logger.info(f"XML Baixado: {num}") 
                except: pass
                
            except Exception as e:
                self.logger.error(f"Erro item {i}: {e}")

    def run(self):
        # Args
        cnpj = self.args.user
        senha = self.args.password
        ons = str(self.args.agente)
        
        # Competencia
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
        
        # Output
        out_dir = self.get_output_path()
        if ons: out_dir = os.path.join(out_dir, ons)

        # Retry Loop
        max_retries = 2
        
        for attempt in range(max_retries + 1):
            if attempt > 0: self.logger.info(f"Tentativa {attempt+1}...")
            
            with sync_playwright() as p:
                browser = p.firefox.launch(headless=True, args=["--start-maximized"])
                context = browser.new_context(accept_downloads=True)
                page = context.new_page()
                state_403 = self.monitor_respostas_403(page)
                
                try:
                    self.logger.info("Acessando CPFL...")
                    page.goto('https://getweb.cpfl.com.br/getweb/getweb.jsf', timeout=90000)
                    
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
                            self.logger.error("Credenciais inválidas.")
                            return
                        raise Exception("Timeout login")

                    if self.pagina_interrompida(page) or state_403['had_403']:
                        raise Exception("Conexão interrompida/403")

                    # Navegação
                    success = self.navegar_para_mes(page, data_site)
                    if not success:
                        self.logger.error("Mês não encontrado.")
                        return

                    # Download
                    self.baixar_documentos(page, ons, out_dir)
                    break # Sucesso

                except Exception as e:
                    self.logger.error(f"Erro: {e}")
                    if attempt == max_retries:
                        self.logger.error("Max tentativas excedido.")
                    time.sleep(5)
                finally:
                    browser.close()

if __name__ == "__main__":
    robot = CPFLRobot()
    robot.run()
