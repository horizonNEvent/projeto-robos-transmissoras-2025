import os
import json
import logging
import sys
import re
import tempfile
import zipfile
import shutil
import urllib3
from pathlib import Path
from datetime import datetime

# Adiciona o diretório da IE ao path para importar a RobotBase
sys.path.append(os.path.join(os.path.dirname(__file__), 'IE'))

try:
    from robot_base import RobotBase, carregar_empresas
except ImportError:
    # Fallback caso o sys.path precise de ajuste adicional
    sys.path.append(os.path.dirname(__file__))
    from IE.robot_base import RobotBase, carregar_empresas

# CONFIGURAÇÃO DE LOGGING
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CTEEP_PBTE")

# Desabilita avisos de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def carregar_credenciais_cteep():
    """Carrega as credenciais específicas para CTEEP do arquivo Data/empresas.cteep.json"""
    try:
        arquivo_json = os.path.join(os.path.dirname(__file__), 'Data', 'empresas.cteep.json')
        if not os.path.exists(arquivo_json):
            logger.error(f"Arquivo não encontrado: {arquivo_json}")
            return []
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar empresas.cteep.json: {e}")
        return []

class CteepPbteRobot(RobotBase):
    def __init__(self):
        # Carrega mapeamento do empresas.json para identificar nomes de pastas se necessário
        mapeamento = {}
        dados_empresas = carregar_empresas()
        if dados_empresas:
            for grupo, lista in dados_empresas.items():
                for emp in lista:
                    mapeamento[str(emp.get('codigo'))] = emp.get('nome')
        
        # Inicializa a base com a URL da Isa Energia Brasil (CTEEP/PBTE)
        super().__init__(
            nome_ie="CTEEP_PBTE",
            url_ie="https://faturamento.isaenergiabrasil.com.br",
            mapeamento_codigos=mapeamento
        )
        
        # Força o uso das credenciais do arquivo específico
        self.credenciais = carregar_credenciais_cteep()

    def download_documentos(self, site_nome, sessao, html, empresa_pasta, ons_pasta):
        """
        Sobrescreve o download original para organizar no padrão: CTEEP_PBTE/[Empresa]/[ONS]
        """
        site_url = self.sites.get(site_nome)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Pasta de destino padronizada (Estilo ASSU)
        destino = Path(self.base_dir) / empresa_pasta / str(ons_pasta)
        destino.mkdir(parents=True, exist_ok=True)

        # Localiza todas as faturas na tabela
        documentos = []
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 3:
                num_fat = cols[2].text.strip()
                if num_fat and num_fat.isdigit():
                    documentos.append(num_fat)

        if not documentos:
            logger.warning(f"[{empresa_pasta}] Nenhuma fatura encontrada no HTML para ONS {ons_pasta}")
            return

        for num_fatura in documentos:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_url_dl = f"{site_url}/download.asp"

                # Pasta específica da Nota Fiscal (NF_XXXXXX)
                pasta_nf = destino / f"NF_{num_fatura}"
                pasta_nf.mkdir(parents=True, exist_ok=True)

                # 1. Download XML/Fatura
                url_xml = f"{base_url_dl}?mode=admin&arquivo=zip&tipo=xml&num_fatura={num_fatura}"
                res_xml = sessao.get(url_xml, verify=False, timeout=30)
                if res_xml.status_code == 200:
                    self._processar_extracao(res_xml.content, num_fatura, pasta_nf, ons_pasta, timestamp)

                # 2. Download Boleto
                url_bol = f"{base_url_dl}?mode=admin&tipo=boleto&arquivo=zip&num_fatura={num_fatura}"
                res_bol = sessao.get(url_bol, verify=False, timeout=30)
                if res_bol.status_code == 200 and len(res_bol.content) > 100:
                    self._processar_extracao(res_bol.content, num_fatura, pasta_nf, ons_pasta, timestamp)

            except Exception as e:
                logger.error(f"Erro ao baixar fatura {num_fatura}: {e}")

    def _processar_extracao(self, conteudo, id_fat, destino_final, ons, ts):
        """Extrai arquivos e salva com a nomenclatura padrão: DOC_IE_[ONS]_[FATURA]_[TS].ext"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(conteudo)
            tmp_path = tmp.name

        try:
            if conteudo.startswith(b'PK'): # É um ZIP
                with zipfile.ZipFile(tmp_path, 'r') as z:
                    for filename in z.namelist():
                        ext = Path(filename).suffix.lower()
                        if ext not in ['.xml', '.pdf']: continue
                        
                        prefix = "NFe_CTEEP" if ext == ".xml" else "DANFE_CTEEP"
                        # Incluímos o número da fatura no nome para ser único
                        final_name = f"{prefix}_{ons}_{id_fat}_{ts}{ext}"
                        
                        with z.open(filename) as source, open(destino_final / final_name, 'wb') as target:
                            target.write(source.read())
                        logger.info(f"[{ons}] NF {id_fat} salva: {final_name}")
            else:
                # Arquivo direto
                ext = ".pdf" if conteudo.startswith(b'%PDF') else ".xml" if b'<?xml' in conteudo else ".dat"
                prefix = "NFe_CTEEP" if ext == ".xml" else "DANFE_CTEEP"
                final_name = f"{prefix}_{ons}_{id_fat}_{ts}{ext}"
                with open(destino_final / final_name, 'wb') as f:
                    f.write(conteudo)
                logger.info(f"[{ons}] NF {id_fat} salva: {final_name}")
        finally:
            if os.path.exists(tmp_path): os.unlink(tmp_path)

    def executar(self):
        """Loop orquestrador que utiliza as credenciais do empresas.cteep.json"""
        logger.info(f"Iniciando processamento para {len(self.credenciais)} acessos da CTEEP.")
        
        for config in self.credenciais:
            empresa = config.get('empresa', 'DESCONHECIDA')
            ons = config.get('codigo_ons', '0000')
            user = config.get('usuario')
            pwd = config.get('senha')

            if not user or not pwd: continue

            logger.info(f"\n--- Processando: {empresa} (ONS: {ons}) ---")
            
            # Orquestração via RobotBase
            sessao = self.login("CTEEP_PBTE", user, pwd)
            if sessao:
                html = self.pesquisar_faturas("CTEEP_PBTE", sessao)
                if html:
                    self.download_documentos("CTEEP_PBTE", sessao, html, empresa, ons)
                    logger.info(f"✓ Sucesso para {empresa} {ons}")
                else:
                    logger.warning(f"! Sem faturas encontradas para {ons}")
            else:
                logger.error(f"X Falha de login para {user}")

def main():
    robot = CteepPbteRobot()
    robot.executar()

if __name__ == "__main__":
    main()