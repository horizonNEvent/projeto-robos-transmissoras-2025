import time
import os
import json
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging
from contextlib import contextmanager

# Configuração de logging (apenas console) - FileHandler removido a pedido
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.FileHandler('grupo_mge_download.log'),  # desabilitado
        logging.StreamHandler()
    ]
)

class GrupoMGEDownloader:
    def __init__(self):
        self.url = "https://ssl5501.websiteseguro.com/transenergia/fatura/index.php"
        self.driver = None
        self.wait = None
        # Caminho específico solicitado - igual ao da assu (modificado para MGE)
        self.download_dir = r"C:\Users\Bruno\Downloads\TUST\MGE"
        self.session = requests.Session()
        
        # Lista das 4 transmissoras
        self.transmissoras = [
            "TRANSENERGIA RENOVÁVEL S.A.",
            "MGE TRANSMISSAO SA",
            "GOIAS TRANSMISSAO SA",
            "TRANSENERGIA SÃO PAULO S.A."
        ]
        
        # Empresas carregadas de Data/empresas.json
        self.empresas_map = self._carregar_empresas()
        # Lista achatada de (codigo, sigla) para processamento
        self.empresas_list = [
            (str(cod), sigla)
            for _secao, mapping in self.empresas_map.items()
            for cod, sigla in mapping.items()
        ]
        
        # Criar diretório de downloads se não existir
        os.makedirs(self.download_dir, exist_ok=True)

    def _carregar_empresas(self):
        """Lê Data/empresas.json e retorna o dicionário de empresas"""
        try:
            # Caminho igual ao da assu
            json_path = os.path.join(os.path.dirname(__file__), 'Data', 'empresas.json')
            if not os.path.exists(json_path):
                logging.error(f"[GRUPOMGE] Arquivo não encontrado: {json_path}")
                return {}
            
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"[GRUPOMGE] Erro ao carregar empresas: {e}")
            return {}

    def _obter_categoria(self, codigo_ons):
        """Retorna RE/AE/DE para um código, com fallback 'OUTROS'"""
        codigo_ons = str(codigo_ons)
        for secao, mapping in self.empresas_map.items():
            if codigo_ons in mapping:
                return secao
        return 'OUTROS'
    
    @contextmanager
    def driver_context(self):
        """Context manager para gerenciar o driver do Chrome de forma segura"""
        driver = None
        try:
            driver = self.setup_driver()
            yield driver
        finally:
            if driver:
                try:
                    driver.quit()
                    logging.info("Driver do Chrome fechado (context manager)")
                except Exception as e:
                    logging.warning(f"Erro ao fechar driver no context manager: {e}")
    
    def setup_driver(self):
        """Configura o driver do Chrome"""
        chrome_options = Options()
        
        # Configurações para download automático
        prefs = {
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "plugins.always_open_pdf_externally": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Outras opções úteis
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--headless")  # Executa sem interface gráfica
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            wait = WebDriverWait(driver, 30)
            logging.info("Driver do Chrome configurado com sucesso (modo headless)")
            return driver, wait
        except Exception as e:
            logging.error(f"Erro ao configurar driver: {e}")
            raise
    
    def criar_pastas_empresa(self, codigo_ons, nome_empresa):
        """Cria as pastas para uma empresa específica"""
        # Determina a categoria da empresa via empresas.json
        categoria = self._obter_categoria(codigo_ons)
        
        # Cria a estrutura de pastas: /AE/4313/, /DE/3748/, /RE/4313/, etc.
        pasta_categoria = os.path.join(self.download_dir, categoria)
        pasta_empresa = os.path.join(pasta_categoria, codigo_ons)
        
        os.makedirs(pasta_empresa, exist_ok=True)
        
        # Criar pastas para cada transmissora
        for transmissora in self.transmissoras:
            pasta_transmissora = os.path.join(pasta_empresa, transmissora)
            os.makedirs(pasta_transmissora, exist_ok=True)
        
        return pasta_empresa
    
    def acessar_site(self, driver, wait):
        """Acessa o site do Grupo MGE"""
        try:
            logging.info(f"Acessando site: {self.url}")
            driver.get(self.url)
            
            # Aguarda a página carregar
            wait.until(EC.presence_of_element_located((By.ID, "codigoONS")))
            logging.info("Site carregado com sucesso")
            
            return True
        except TimeoutException:
            logging.error("Timeout ao carregar o site")
            return False
        except Exception as e:
            logging.error(f"Erro ao acessar site: {e}")
            return False
    
    def fazer_login(self, driver, wait, codigo_ons):
        """Faz login com o código ONS"""
        try:
            logging.info(f"Fazendo login com código ONS: {codigo_ons}")
            
            # Localiza e preenche o campo do código ONS
            campo_ons = wait.until(EC.element_to_be_clickable((By.ID, "codigoONS")))
            campo_ons.clear()
            campo_ons.send_keys(codigo_ons)
            
            # Clica no botão de acessar
            botao_acessar = wait.until(EC.element_to_be_clickable((By.ID, "btnAcessar")))
            botao_acessar.click()
            
            # Aguarda a página de faturas carregar
            time.sleep(3)
            
            logging.info("Login realizado com sucesso")
            return True
            
        except TimeoutException:
            logging.error("Timeout ao fazer login")
            return False
        except Exception as e:
            logging.error(f"Erro ao fazer login: {e}")
            return False
    
    def verificar_acesso(self, driver):
        """Verifica se o acesso foi bem-sucedido"""
        try:
            # Aguarda um pouco para a página carregar completamente
            time.sleep(5)
            
            # Verifica se há elementos que indicam sucesso no login
            current_url = driver.current_url
            page_source = driver.page_source
            
            logging.info(f"URL atual: {current_url}")
            
            # Verifica se ainda está na página de login (indicando erro)
            if "index.php" in current_url and "codigoONS" in page_source:
                logging.warning("Ainda na página de login - possível erro no código ONS")
                return False
            
            # Verifica se conseguiu acessar a seção de faturas
            if "faturas" in page_source and "table" in page_source:
                logging.info("Acesso verificado com sucesso - página de faturas carregada")
                return True
            
            logging.info("Acesso verificado com sucesso")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao verificar acesso: {e}")
            return False
    
    def filtrar_por_mes(self, faturas, mes, ano=None):
        """Filtra faturas por mês de emissão específico"""
        faturas_filtradas = []
        
        for fatura in faturas:
            try:
                # Converte data de emissão para objeto datetime
                data_emissao = datetime.strptime(fatura['emissao'], '%d/%m/%Y')
                
                # Verifica se o mês corresponde
                if data_emissao.month == mes:
                    # Se ano foi especificado, verifica também
                    if ano is None or data_emissao.year == ano:
                        faturas_filtradas.append(fatura)
                
            except ValueError:
                # Se não conseguir converter a data, pula a fatura
                continue
        
        return faturas_filtradas
    
    def extrair_dados_faturas(self, driver, wait):
        """Extrai os dados da tabela de faturas"""
        try:
            logging.info("Extraindo dados da tabela de faturas...")
            
            # Aguarda a tabela carregar
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table")))
            
            # Encontra todas as linhas da tabela (exceto cabeçalho)
            linhas = driver.find_elements(By.CSS_SELECTOR, "table.table tbody tr")
            
            faturas = []
            
            for linha in linhas:
                try:
                    # Extrai os dados de cada coluna
                    colunas = linha.find_elements(By.TAG_NAME, "td")
                    
                    if len(colunas) >= 6:  # Verifica se tem todas as colunas necessárias
                        fatura = {
                            'estabelecimento': colunas[0].text.strip(),
                            'emissao': colunas[1].text.strip(),
                            'vencimento': colunas[2].text.strip(),
                            'numero_nota': colunas[3].text.strip(),
                            'valor': colunas[4].text.strip(),
                            'links': {}
                        }
                        
                        # Extrai os links de XML, DANFE e Boleto
                        links = linha.find_elements(By.TAG_NAME, "a")
                        for link in links:
                            href = link.get_attribute("href")
                            texto = link.text.strip()
                            
                            if "XML" in texto:
                                fatura['links']['xml'] = href
                            elif "DANFE" in texto:
                                fatura['links']['danfe'] = href
                            elif "Boleto" in texto:
                                fatura['links']['boleto'] = href
                        
                        faturas.append(fatura)
                        logging.info(f"Fatura extraída: {fatura['estabelecimento']} - {fatura['numero_nota']}")
                
                except Exception as e:
                    logging.warning(f"Erro ao extrair linha da tabela: {e}")
                    continue
            
            logging.info(f"Total de faturas extraídas: {len(faturas)}")
            return faturas
            
        except Exception as e:
            logging.error(f"Erro ao extrair dados das faturas: {e}")
            return []
    
    def baixar_arquivo(self, url, nome_arquivo, pasta_transmissora, driver):
        """Baixa um arquivo usando requests e salva na pasta da transmissora"""
        try:
            logging.info(f"Baixando: {nome_arquivo}")
            
            # Configura headers para simular navegador
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': driver.current_url
            }
            
            # Copia cookies do Selenium para o requests
            selenium_cookies = driver.get_cookies()
            for cookie in selenium_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
            
            # Faz o download
            response = self.session.get(url, headers=headers, stream=True)
            response.raise_for_status()
            
            # Salva o arquivo na pasta da transmissora
            caminho_arquivo = os.path.join(pasta_transmissora, nome_arquivo)
            with open(caminho_arquivo, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logging.info(f"Arquivo baixado com sucesso: {caminho_arquivo}")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao baixar {nome_arquivo}: {e}")
            return False
    
    def baixar_faturas_por_transmissora(self, faturas_filtradas, pasta_empresa, driver, nome_empresa):
        """Baixa os arquivos XML, DANFE e boletos das faturas organizados por transmissora"""
        try:
            logging.info(f"Iniciando download de faturas para {nome_empresa} por transmissora...")
            
            total_faturas = len(faturas_filtradas)
            arquivos_baixados = 0
            
            # Agrupa faturas por transmissora
            faturas_por_transmissora = {}
            for transmissora in self.transmissoras:
                faturas_por_transmissora[transmissora] = []
            
            for fatura in faturas_filtradas:
                estabelecimento = fatura['estabelecimento']
                if estabelecimento in faturas_por_transmissora:
                    faturas_por_transmissora[estabelecimento].append(fatura)
            
            # Baixa arquivos para cada transmissora
            for transmissora, faturas in faturas_por_transmissora.items():
                if not faturas:
                    logging.info(f"Nenhuma fatura encontrada para: {transmissora}")
                    continue
                
                logging.info(f"Processando {len(faturas)} faturas de: {transmissora}")
                
                # Cria pasta da transmissora dentro da pasta da empresa
                pasta_transmissora = os.path.join(pasta_empresa, transmissora)
                
                for fatura in faturas:
                    logging.info(f"Processando fatura: {fatura['estabelecimento']} - {fatura['numero_nota']}")
                    
                    # Baixa XML se disponível - Nome formatado igual assu
                    if 'xml' in fatura['links']:
                        nome_xml = f"NFe_{nome_empresa}_{fatura['numero_nota']}.xml"
                        caminho_xml = os.path.join(pasta_transmissora, nome_xml)
                        if os.path.exists(caminho_xml):
                            logging.info(f"Arquivo já existe, pulando: {nome_xml}")
                        else:
                            if self.baixar_arquivo(fatura['links']['xml'], nome_xml, pasta_transmissora, driver):
                                arquivos_baixados += 1
                    
                    # Baixa DANFE se disponível - Nome formatado igual assu
                    if 'danfe' in fatura['links']:
                        nome_danfe = f"DANFE_{nome_empresa}_{fatura['numero_nota']}.pdf"
                        caminho_danfe = os.path.join(pasta_transmissora, nome_danfe)
                        if os.path.exists(caminho_danfe):
                            logging.info(f"Arquivo já existe, pulando: {nome_danfe}")
                        else:
                            if self.baixar_arquivo(fatura['links']['danfe'], nome_danfe, pasta_transmissora, driver):
                                arquivos_baixados += 1
                    
                    # Baixa boleto se disponível - Nome formatado igual assu
                    if 'boleto' in fatura['links']:
                        nome_boleto = f"Boleto_{nome_empresa}_{fatura['numero_nota']}.pdf"
                        caminho_boleto = os.path.join(pasta_transmissora, nome_boleto)
                        if os.path.exists(caminho_boleto):
                            logging.info(f"Arquivo já existe, pulando: {nome_boleto}")
                        else:
                            if self.baixar_arquivo(fatura['links']['boleto'], nome_boleto, pasta_transmissora, driver):
                                arquivos_baixados += 1
                    
                    # Pequena pausa entre downloads
                    time.sleep(1)
            
            logging.info(f"Download concluído: {arquivos_baixados} arquivos baixados")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao baixar faturas: {e}")
            return False
    
    def processar_empresa(self, codigo_ons, nome_empresa, mes, ano):
        """Processa uma empresa específica"""
        try:
            logging.info(f"=== PROCESSANDO EMPRESA: {nome_empresa} (ONS: {codigo_ons}) - MÊS: {mes}/{ano} ===")
            
            # Criar pastas para a empresa
            pasta_empresa = self.criar_pastas_empresa(codigo_ons, nome_empresa)
            
            # Usar context manager para gerenciar o driver de forma segura
            with self.driver_context() as (driver, wait):
                # Passo 1: Acessar o site
                if not self.acessar_site(driver, wait):
                    logging.error(f"Falha ao acessar site para empresa {nome_empresa}")
                    return False
                
                # Passo 2: Fazer login
                if not self.fazer_login(driver, wait, codigo_ons):
                    logging.error(f"Falha no login para empresa {nome_empresa}")
                    return False
                
                # Passo 3: Verificar se o acesso foi bem-sucedido
                if not self.verificar_acesso(driver):
                    logging.error(f"Falha na verificação de acesso para empresa {nome_empresa}")
                    return False
                
                # Passo 4: Extrair dados das faturas
                todas_faturas = self.extrair_dados_faturas(driver, wait)
                if not todas_faturas:
                    logging.info(f"Nenhuma fatura encontrada para empresa {nome_empresa}")
                    return True  # Não é erro, apenas não há faturas
                
                # Passo 5: Filtrar faturas do mês atual; se vazio, usar mês mais recente disponível
                faturas_filtradas = self.filtrar_por_mes(todas_faturas, mes=mes, ano=ano)
                if not faturas_filtradas:
                    # Encontrar mês mais recente nas faturas
                    datas_validas = []
                    for f in todas_faturas:
                        try:
                            datas_validas.append(datetime.strptime(f['emissao'], '%d/%m/%Y'))
                        except Exception:
                            continue
                    if datas_validas:
                        mais_recente = max(datas_validas)
                        alt_mes, alt_ano = mais_recente.month, mais_recente.year
                        logging.info(
                            f"Nenhuma fatura para {mes:02d}/{ano}. Usando mês mais recente disponível: {alt_mes:02d}/{alt_ano}."
                        )
                        faturas_filtradas = self.filtrar_por_mes(todas_faturas, mes=alt_mes, ano=alt_ano)
                    if not faturas_filtradas:
                        logging.info(f"Nenhuma fatura do mês {mes}/{ano} (nem meses recentes) encontrada para empresa {nome_empresa}")
                        return True  # Não é erro, apenas não há faturas
                
                logging.info(f"Faturas do mês {mes}/{ano} encontradas para {nome_empresa}: {len(faturas_filtradas)}")
                
                # Mostra as faturas encontradas
                for fatura in faturas_filtradas:
                    logging.info(f"  - {fatura['estabelecimento']} - {fatura['numero_nota']} - {fatura['emissao']} - R$ {fatura['valor']}")
                
                # Passo 6: Baixar faturas organizadas por transmissora - agora passando nome_empresa para o nome do arquivo
                self.baixar_faturas_por_transmissora(faturas_filtradas, pasta_empresa, driver, nome_empresa)
                
                logging.info(f"=== EMPRESA {nome_empresa} PROCESSADA COM SUCESSO ===")
                return True
            
        except Exception as e:
            logging.error(f"Erro durante processamento da empresa {nome_empresa}: {e}")
            return False
    
    def executar_automacao_completa(self, mes, ano):
        """Executa a automação para todas as empresas"""
        try:
            logging.info(f"=== INICIANDO AUTOMAÇÃO COMPLETA GRUPO MGE - MÊS {mes}/{ano} ===")
            
            # Lista todas as empresas a partir do empresas.json
            todas_empresas = list(self.empresas_list)
            
            logging.info(f"Total de empresas a processar: {len(todas_empresas)}")
            
            empresas_processadas = 0
            empresas_com_erro = 0
            
            # Processa cada empresa
            for i, (codigo_ons, nome_empresa) in enumerate(todas_empresas, 1):
                try:
                    logging.info(f"Progresso: {i}/{len(todas_empresas)} - Empresa: {nome_empresa} (ONS: {codigo_ons})")
                    
                    sucesso = self.processar_empresa(codigo_ons, nome_empresa, mes, ano)
                    if sucesso:
                        empresas_processadas += 1
                    else:
                        empresas_com_erro += 1
                    
                    # Pequena pausa entre empresas
                    time.sleep(2)
                    
                except Exception as e:
                    logging.error(f"Erro inesperado ao processar empresa {nome_empresa}: {e}")
                    empresas_com_erro += 1
                    continue
            
            logging.info("=== AUTOMAÇÃO COMPLETA FINALIZADA ===")
            logging.info(f"Empresas processadas com sucesso: {empresas_processadas}")
            logging.info(f"Empresas com erro: {empresas_com_erro}")
            
            return True
            
        except Exception as e:
            logging.error(f"Erro durante a automação completa: {e}")
            return False
    
    def __del__(self):
        """Destrutor para garantir que o driver seja fechado"""
        pass  # Não é mais necessário pois usamos context manager

def main():
    """Função principal"""
    print("🚀 BAIXANDO FATURAS - GRUPO MGE (TODAS AS EMPRESAS)")
    print("=" * 70)
    
    # Usar automaticamente o mês e ano atuais
    agora = datetime.now()
    mes = agora.month
    ano = agora.year
    
    print(f"📅 Baixando faturas do mês atual: {mes:02d}/{ano}")
    print("=" * 70)
    
    # Criar instância do downloader
    downloader = GrupoMGEDownloader()
    
    # Executar automação completa
    sucesso = downloader.executar_automacao_completa(mes=mes, ano=ano)
    
    if sucesso:
        print("\n✅ Automação executada com sucesso!")
        print(f"📁 Arquivos salvos em: {downloader.download_dir}")
        print("\n📋 Transmissoras processadas:")
        for transmissora in downloader.transmissoras:
            print(f"  - {transmissora}")
        
        # Mostra estatísticas das empresas
        total_empresas = sum(len(mapping) for mapping in downloader.empresas_map.values())
        print(f"\n📊 Total de empresas: {total_empresas}")
        for grupo, mapping in downloader.empresas_map.items():
            print(f"  - {grupo}: {len(mapping)} empresas")
    else:
        print("\n❌ Erro na execução da automação. Verifique os logs.")

if __name__ == "__main__":
    main()
