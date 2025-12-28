import os
import time
import json
import logging
import urllib3
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

# CONFIGURAÇÃO DE LOGGING
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurações globais
BASE_DIR_DOWNLOAD = r"C:\Users\Bruno\Downloads\TUST\CPFL"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def carregar_empresas_cpfl():
    """Carrega as informações das empresas do arquivo Data/empresas_cpfl.json"""
    try:
        arquivo_json = os.path.join(os.path.dirname(__file__), 'Data', 'empresas_cpfl.json')
        if not os.path.exists(arquivo_json):
            logger.error(f"Arquivo não encontrado: {arquivo_json}")
            return None
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar JSON: {e}")
        return None

def obter_data_cpfl():
    """Retorna dados do mês de referência (mês anterior)"""
    data_atual = datetime.now()
    if data_atual.month == 1:
        mes, ano = 12, data_atual.year - 1
    else:
        mes, ano = data_atual.month - 1, data_atual.year
    data_site = f"{mes:02d}/{ano}"
    return mes, ano, data_site

def baixar_documentos(page, agent_info, empresa_nome, mapeamento):
    time.sleep(3)
    ons_nome = agent_info["nome"]
    codigo_ons = agent_info["codigo"]
    
    # Determina o texto de busca baseado no mapeamento (Fluxo do script funcional)
    nome_fatura = mapeamento.get(ons_nome, mapeamento.get("*", ons_nome))
    
    logger.info(f"[{empresa_nome}] Buscando faturas com texto: {nome_fatura} - Fatura")
    
    faturas = page.locator(f'text={nome_fatura} - Fatura')
    count = faturas.count()
    logger.info(f"[{empresa_nome}] Encontrados {count} itens de fatura.")
    
    if count == 0:
        return

    destino_base = Path(BASE_DIR_DOWNLOAD) / empresa_nome / str(codigo_ons)

    for i in range(count):
        try:
            logger.info(f"[{empresa_nome}] Processando fatura {i+1}/{count}")
            fatura_item = faturas.nth(i)
            text = fatura_item.inner_text()
            
            # Extração do número da fatura
            try:
                num_nf = text.split('Nº: ')[1].split(' -')[0].strip().replace('.', '').replace('/', '').replace('-', '')
            except:
                num_nf = f"Fatura_{i+1}"

            # Criar subpasta para a NF específica
            pasta_nf = destino_base / f"NF_{num_nf}"
            pasta_nf.mkdir(parents=True, exist_ok=True)

            # O fluxo secreto: clicar no TreeNode via ID padronizado n-0-{i}
            fatura_selector = f'span[class="iceOutTxt"][id="form:tree:n-0-{i}:TreeNode"]'
            try:
                page.click(fatura_selector, timeout=5000)
                logger.info(f"[{empresa_nome}] Clicou no TreeNode. Aguardando ícones...")
            except:
                fatura_item.click()
            
            time.sleep(2)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # DOWNLOAD PDF
            try:
                pdf_icon = page.locator('img[src*="pdf_ico.png"]').last
                if pdf_icon.is_visible(timeout=10000):
                    with page.expect_download() as download_info:
                        pdf_icon.click()
                        download = download_info.value
                        nome_pdf = f"DANFE_CPFL_{num_nf}_{timestamp}.pdf"
                        download.save_as(pasta_nf / nome_pdf)
                    logger.info(f"[{empresa_nome}] ✅ PDF salvo em {num_nf}")
            except: pass

            # DOWNLOAD XML
            try:
                link_nf = page.locator('text=Nota Fiscal Modelo').nth(i)
                if link_nf.is_visible(timeout=3000):
                    link_nf.click()
                    time.sleep(1)
                    xml_icon = page.locator('img[src*="xml"]').last
                    if xml_icon.is_visible(timeout=5000):
                        with page.expect_download() as download_info:
                            xml_icon.click()
                            download = download_info.value
                            nome_xml = f"NFe_CPFL_{num_nf}_{timestamp}.xml"
                            download.save_as(pasta_nf / nome_xml)
                        logger.info(f"[{empresa_nome}] ✅ XML salvo em {num_nf}")
            except: pass

        except Exception as e:
            logger.error(f"Erro no item {i}: {e}")

def processar_agente(agent_info, empresa_nome, data_site, mapeamento):
    logger.info(f"🚀 Iniciando Agente: {agent_info['nome']} ({agent_info['codigo']})")
    
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        
        try:
            page.goto('https://getweb.cpfl.com.br/getweb/getweb.jsf', timeout=60000)
            
            # Login
            page.fill('#form\\:documento', agent_info['cnpj'])
            page.fill('#form\\:senha', agent_info['senha'])
            page.click('#form\\:j_idt22')
            
            page.wait_for_selector('.iceTree', timeout=60000)
            time.sleep(5)
            
            # Navegação no Mês (Fluxo do script funcional)
            data_element = page.locator(f"span.iceOutTxt:has-text('{data_site}')")
            if data_element.count() > 0:
                node_id = data_element.first.evaluate("el => el.closest('.iceTreeRow').id")
                node_number = node_id.split('-')[-1]
                logger.info(f"Nó do mês {data_site} encontrado: {node_number}")
                
                # Expandir Mês
                page.locator(f"#form\\:tree\\:{node_number}").click()
                time.sleep(4)
                
                # Expandir subpastas (Galhos dos Agentes)
                sub_selector = f'#form\\:tree-d-{node_number} a[id^="form:tree"]'
                sub_count = page.locator(sub_selector).count()
                logger.info(f"Expandindo {sub_count} subpastas...")
                
                for j in range(sub_count):
                    try:
                        sub_node = page.locator(f"#form\\:tree\\:{node_number}-{j}")
                        if sub_node.is_visible():
                            sub_node.click()
                            time.sleep(1)
                    except: pass
                
                # Inicia busca e download
                baixar_documentos(page, agent_info, empresa_nome, mapeamento)
                logger.info(f"✅ Finalizado: {agent_info['nome']}")
            else:
                logger.error(f"Mês referência {data_site} não encontrado.")

        except Exception as e:
            logger.error(f"❌ Erro fatal: {e}")
        finally:
            browser.close()

def main():
    dados = carregar_empresas_cpfl()
    if not dados: return
        
    mes, ano, data_site = obter_data_cpfl()
    mapeamento = dados.get("mapeamento_empresas", {})
    
    for empresa_nome, lista_agentes in dados.items():
        if empresa_nome == "mapeamento_empresas": continue
        
        logger.info(f"\n=== Empresa: {empresa_nome} ===")
        for agent in lista_agentes:
            processar_agente(agent, empresa_nome, data_site, mapeamento)
            time.sleep(3)

if __name__ == "__main__":
    main()