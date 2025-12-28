import os
import sys
import time
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Configuração do LOG
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR_DOWNLOAD = r"C:\Users\Bruno\Downloads\TUST\CELEO"

def carregar_empresas():
    """Carrega as informações das empresas do arquivo Data/empresas.json"""
    try:
        arquivo_json = os.path.join(os.path.dirname(__file__), 'Data', 'empresas.json')
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar empresas: {str(e)}")
        return {}

def salvar_boleto_pdf(context, boleto_url, dest_path):
    """Abre o boleto em uma nova aba e salva como PDF."""
    try:
        if not boleto_url: return False
        if boleto_url.startswith("/"): boleto_url = "https://boleto.celeoredes.com.br" + boleto_url
        if not boleto_url.startswith("http"): boleto_url = "https://boleto.celeoredes.com.br/" + boleto_url

        print_page = context.new_page()
        try:
            print_page.goto(boleto_url, wait_until="networkidle", timeout=30000)
            html = print_page.content()
            if "Not Found" in html or "requested URL was not found" in html:
                alt = None
                if boleto_url.startswith("https://"): alt = "http://" + boleto_url[len("https://"):]
                elif boleto_url.startswith("http://"): alt = "https://" + boleto_url[len("http://"):]
                if alt: print_page.goto(alt, wait_until="networkidle", timeout=30000)

            time.sleep(1)
            print_page.emulate_media(media="print")
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            print_page.pdf(
                path=str(dest_path),
                format="A4",
                print_background=True,
                margin={"top": "5mm", "right": "5mm", "bottom": "5mm", "left": "5mm"}
            )
            return True
        finally:
            print_page.close()
    except Exception as e:
        logger.error(f"Erro ao salvar boleto PDF: {e}")
        return False

def processar_celeo(p, codigo_ons, empresa_nome, nome_ons):
    url = "https://boleto.celeoredes.com.br/"
    base_save_path = Path(BASE_DIR_DOWNLOAD) / empresa_nome / str(codigo_ons)
    
    logger.info(f"[{empresa_nome}] Iniciando CELEO para ONS {codigo_ons}")

    browser = p.chromium.launch(headless=True)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector("#txtNordem", timeout=30000)
        page.fill("#txtNordem", codigo_ons)
        page.click("#btnBusca")
        time.sleep(2)

        # Seleciona o mês vigente
        try:
            page.wait_for_selector("select[name='cmbPeriodo']", timeout=5000)
            mes_atual = str(datetime.now().month)
            page.select_option("select[name='cmbPeriodo']", mes_atual)
            time.sleep(2)
        except: pass

        # Captura de registros usando Regex corrigida e string bruta
        records = page.evaluate(r"""
            () => {
                const els = Array.from(document.querySelectorAll("input[type='button'][onclick]"));
                const out = [];
                for (const el of els) {
                    const onclick = String(el.getAttribute('onclick') || '');
                    if (!onclick.includes('XML')) continue;
                    
                    const m = onclick.match(/usageWindowOpen\s*\(\s*'([^']+)'/);
                    const chave = m ? m[1] : '';
                    
                    const tr = el.closest('tr');
                    const tds = tr ? Array.from(tr.querySelectorAll('td')) : [];
                    const transmissora = tds.length ? tds[0].innerText.trim() : 'SEM_NOME';
                    
                    let boletoHref = '';
                    if (tr) {
                        let a = tr.querySelector("a[href*='boleto']");
                        if (!a) {
                            a = Array.from(tr.querySelectorAll('a')).find(x => {
                                const img = x.querySelector('img');
                                return img && (/printer/i.test(img.getAttribute('src')||'') || /print/i.test(img.getAttribute('alt')||''));
                            });
                        }
                        if (a) boletoHref = a.getAttribute('href') || a.href || '';
                    }
                    out.push({ chave, transmissora, boletoHref });
                }
                return out;
            }
        """)

        for rec in records:
            transmissora_clean = rec['transmissora'].replace(' ', '_').replace('/', '-')
            chave = rec['chave']
            path_transmissora = base_save_path / transmissora_clean
            path_transmissora.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # 1. Download XML usando popup handling
            try:
                with context.expect_page(timeout=10000) as pinfo:
                    page.evaluate(f"usageWindowOpen('{chave}', 'XML')")
                popup = pinfo.value
                popup.wait_for_load_state("domcontentloaded")
                xml_content = popup.content()
                
                if "<?xml" in xml_content or "<NFe" in xml_content:
                    xml_path = path_transmissora / f"NFe_{transmissora_clean}_{timestamp}.xml"
                    xml_path.write_text(xml_content, encoding="utf-8")
                    logger.info(f"[{empresa_nome}] XML salvo: {xml_path.name}")
                popup.close()
            except Exception as e:
                logger.error(f"Erro ao capturar XML para {transmissora_clean}: {e}")

            # 2. Download Boleto
            if rec['boletoHref']:
                boleto_path = path_transmissora / f"Boleto_{transmissora_clean}_{timestamp}.pdf"
                if salvar_boleto_pdf(context, rec['boletoHref'], boleto_path):
                    logger.info(f"[{empresa_nome}] Boleto salvo: {boleto_path.name}")

    finally:
        browser.close()

def main():
    if not (Path(__file__).parent / 'Data' / 'empresas.json').exists():
        logger.error("Arquivo Data/empresas.json não encontrado.")
        return

    empresas = carregar_empresas()
    with sync_playwright() as p:
        for empresa_nome, ons_dict in empresas.items():
            logger.info(f"\n=== Empresa: {empresa_nome} ===")
            for ons_code, nome_ons in ons_dict.items():
                try:
                    processar_celeo(p, str(ons_code), empresa_nome, nome_ons)
                except Exception as e:
                    logger.error(f"Erro ao processar {empresa_nome} ONS {ons_code}: {e}")

if __name__ == "__main__":
    main()
