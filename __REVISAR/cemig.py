import requests
from bs4 import BeautifulSoup
import os
import time
import re
import shutil
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import threading
from concurrent.futures import ThreadPoolExecutor

# Carregar o arquivo empresas.json
with open(os.path.join(os.path.dirname(__file__), 'Data/empresas.json'), 'r', encoding='utf-8') as f:
    EMPRESAS = json.load(f)

class AEDownloader:
    def __init__(self, empresa_mae=None, cod_ons=None, nome_ons=None, download_path=None, headless=True):
        """
        Inicializa o downloader da AE
        
        Args:
            empresa_mae: Nome da empresa mãe (ex: AETE)
            cod_ons: Código ONS da empresa
            nome_ons: Nome da empresa no ONS
            download_path: Caminho base para salvar os arquivos baixados
            headless: Se True, executa o Chrome em modo headless (sem interface gráfica)
        """
        self.empresa_mae = empresa_mae
        self.cod_ons = cod_ons
        self.nome_ons = nome_ons

        # Definir o caminho de download BASE
        if download_path is None:
            self.base_path = r"C:\Users\Bruno\Downloads\TUST\CEMIG"
        else:
            self.base_path = download_path
        
        # O Chrome sempre baixa na base primeiro para evitarmos confusão entre instâncias
        self.download_path = self.base_path
        os.makedirs(self.download_path, exist_ok=True)
        
        # Criar a pasta final de destino (Padrão ASSU: CEMIG/Empresa/Codigo)
        self.pastas_empresas = {}
        if empresa_mae and cod_ons:
            pasta_final = os.path.join(self.base_path, empresa_mae, cod_ons)
            os.makedirs(pasta_final, exist_ok=True)
            self.pastas_empresas[cod_ons] = pasta_final
            self.final_path = pasta_final
        else:
            self.final_path = self.download_path
            self.empresas = {}
        
        # Configurar o Chrome para baixar arquivos automaticamente para o diretório especificado
        self.chrome_options = Options()
        self.chrome_options.add_experimental_option("prefs", {
            "download.default_directory": self.download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        })
        
        # Configurar modo headless se solicitado
        if headless:
            self.chrome_options.add_argument("--headless")
            self.chrome_options.add_argument("--window-size=1920,1080")
        
        # Inicializar o driver do Chrome
        self.driver = webdriver.Chrome(options=self.chrome_options)
        self.base_url = "https://web.cemig.com.br/frbe"
        
    def iniciar_sessao(self):
        """Inicia a sessão no site da CEMIG"""
        try:
            self.driver.get(self.base_url)
            print("Sessão iniciada com sucesso")
            return True
        except Exception as e:
            print(f"Erro ao iniciar sessão: {e}")
            return False
    
    def verificar_javascript(self):
        """Verifica se o JavaScript está sendo executado corretamente"""
        try:
            # Tentar executar um JavaScript simples
            resultado = self.driver.execute_script("return document.readyState")
            print(f"Estado do documento: {resultado}")
            
            # Verificar se a função VisualizarArquivo existe
            existe_funcao = self.driver.execute_script("return typeof VisualizarArquivo !== 'undefined'")
            if existe_funcao:
                print("Função VisualizarArquivo encontrada!")
            else:
                print("Função VisualizarArquivo NÃO encontrada.")
            
            return True
        except Exception as e:
            print(f"Erro ao verificar JavaScript: {e}")
            return False
    
    def pesquisar_empresa(self, codigo_empresa):
        """Pesquisa a empresa pelo código ONS"""
        try:
            # Encontrar o campo de entrada e inserir o código
            input_ons = self.driver.find_element(By.ID, "ONS")
            input_ons.clear()
            input_ons.send_keys(codigo_empresa)
            
            print(f"Inserido código da empresa: {codigo_empresa}")
            
            # Verificar o elemento de loading
            loading_element = self.driver.find_element(By.ID, "loading")
            print(f"Estado inicial do loading: {loading_element.get_attribute('style')}")
            
            # Clicar no botão de pesquisa
            botao_pesquisar = self.driver.find_element(By.ID, "btnPesquisar")
            botao_pesquisar.click()
            
            print("Botão de pesquisa clicado, aguardando carregamento...")
            
            # Aguardar que o elemento de loading apareça
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda driver: "display: none" not in driver.find_element(By.ID, "loading").get_attribute("style")
                )
                print("Loading visível, aguardando processamento...")
            except Exception as e:
                print(f"Elemento de loading não ficou visível: {e}")
                print("Tentando continuar mesmo assim...")
            
            # Aguardar que o elemento de loading desapareça - COM TEMPO MAIOR
            max_espera = 60  # Aumentar para 60 segundos
            print(f"Aguardando até {max_espera} segundos para o processamento terminar...")
            
            try:
                WebDriverWait(self.driver, max_espera).until(
                    lambda driver: "display: none" in driver.find_element(By.ID, "loading").get_attribute("style")
                )
                print("Processamento concluído! Loading desapareceu.")
            except Exception as e:
                print(f"Timeout esperando o loading desaparecer: {e}")
                print("Verificando estado atual do loading...")
                
                try:
                    loading_atual = self.driver.find_element(By.ID, "loading").get_attribute("style")
                    print(f"Estado atual do loading: {loading_atual}")
                    
                    if "display: none" in loading_atual:
                        print("Loading está invisível agora, podemos continuar.")
                    else:
                        print("Loading ainda está visível, mas vamos tentar continuar...")
                        
                        # Tentar forçar o loading a desaparecer via JavaScript
                        self.driver.execute_script("document.getElementById('loading').style.display = 'none';")
                        print("Forçado loading a desaparecer via JavaScript")
                except Exception as load_err:
                    print(f"Erro ao verificar loading: {load_err}")
            
            # Aguardar um tempo fixo para garantir
            print("Aguardando 5 segundos adicionais...")
            time.sleep(5)
            
            # Verificar se a div contentAjax foi preenchida
            content_ajax = self.driver.find_element(By.CLASS_NAME, "contentAjax")
            content_html = content_ajax.get_attribute("innerHTML").strip()
            
            print(f"Conteúdo da div contentAjax: {len(content_html)} caracteres")
            
            if len(content_html) < 10:  # Se estiver praticamente vazia
                print("A div contentAjax parece vazia. Tentando abordagem alternativa...")
                
                # Tentar executar o JavaScript diretamente com token de verificação
                try:
                    # Obter o token de verificação
                    token = self.driver.execute_script("""
                        return $('input[name="__RequestVerificationToken"]').val();
                    """)
                    
                    print(f"Token de verificação: {token[:10]}...")
                    
                    # Reenviar a requisição AJAX manualmente com o token
                    ajax_result = self.driver.execute_script("""
                        var result;
                        $.ajax({
                            url: '/FRBE/Home/Pesquisar',
                            type: 'POST',
                            data: { 
                                ONS: arguments[0],
                                __RequestVerificationToken: arguments[1]
                            },
                            async: false,
                            success: function(data) {
                                result = data;
                                $('.contentAjax').html(data);
                            }
                        });
                        return result;
                    """, codigo_empresa, token)
                    
                    print("Requisição AJAX executada manualmente com token")
                    
                    # Aguardar um pouco mais
                    time.sleep(5)
                    
                    # Verificar novamente o conteúdo
                    content_ajax = self.driver.find_element(By.CLASS_NAME, "contentAjax")
                    content_html = content_ajax.get_attribute("innerHTML").strip()
                    print(f"Novo conteúdo da div contentAjax: {len(content_html)} caracteres")
                except Exception as ajax_error:
                    print(f"Erro ao executar AJAX manualmente: {ajax_error}")
                    
                    # Tentar uma abordagem mais direta - recarregar a página e tentar novamente
                    print("Tentando abordagem mais direta...")
                    
                    # Recarregar a página
                    self.driver.refresh()
                    time.sleep(3)
                    
                    # Encontrar o campo de entrada e inserir o código novamente
                    input_ons = self.driver.find_element(By.ID, "ONS")
                    input_ons.clear()
                    input_ons.send_keys(codigo_empresa)
                    
                    # Clicar no botão de pesquisa novamente
                    botao_pesquisar = self.driver.find_element(By.ID, "btnPesquisar")
                    botao_pesquisar.click()
                    
                    # Aguardar mais tempo
                    print("Aguardando 20 segundos após nova tentativa...")
                    time.sleep(20)
                    
                    # Verificar novamente o conteúdo
                    content_ajax = self.driver.find_element(By.CLASS_NAME, "contentAjax")
                    content_html = content_ajax.get_attribute("innerHTML").strip()
                    print(f"Conteúdo após nova tentativa: {len(content_html)} caracteres")
            
            # Verificar se há links de download
            links = self.driver.find_elements(By.TAG_NAME, "a")
            links_download = [link for link in links if "VisualizarArquivo" in (link.get_attribute("onclick") or "")]
            
            print(f"Encontrados {len(links_download)} links de download")
            
            if not links_download:
                print("Nenhum link de download encontrado. Tentando uma última abordagem...")
                
                # Salvar screenshot para diagnóstico
                screenshot_path = os.path.join(self.download_path, f"sem_links_{codigo_empresa}.png")
                self.driver.save_screenshot(screenshot_path)
                print(f"Screenshot salvo em: {screenshot_path}")
                
                # Salvar HTML para diagnóstico
                with open(os.path.join(self.download_path, f"pagina_sem_links_{codigo_empresa}.html"), "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                
                return False
            
            print(f"Pesquisa para empresa {codigo_empresa} realizada com sucesso")
            return True
        except Exception as e:
            print(f"Erro ao pesquisar empresa: {e}")
            
            # Salvar screenshot para diagnóstico
            screenshot_path = os.path.join(self.download_path, f"erro_{codigo_empresa}.png")
            self.driver.save_screenshot(screenshot_path)
            print(f"Screenshot salvo em: {screenshot_path}")
            
            return False
    
    def baixar_arquivos(self, codigo_empresa, tipo_arquivo=None):
        """Baixa os arquivos encontrados na página de resultados"""
        try:
            # Encontrar todos os links com VisualizarArquivo na página
            links = self.driver.find_elements(By.TAG_NAME, "a")
            links_download = [link for link in links if "VisualizarArquivo" in (link.get_attribute("onclick") or "")]
            
            print(f"Encontrados {len(links_download)} links de download")
            
            if not links_download:
                print("Nenhum link de download encontrado.")
                return False
            
            # Dicionário para mapear nomes de arquivos para textos dos links
            self.mapeamento_arquivos = {}
            
            # Contador para acompanhar os downloads
            downloads_realizados = 0
            arquivos_baixados = []
            
            for link in links_download:
                texto_link = link.text.strip()
                onclick = link.get_attribute("onclick")
                
                # Verificar se o link corresponde ao tipo de arquivo desejado
                if tipo_arquivo:
                    if tipo_arquivo.lower() == "boleto" and "boleto" not in texto_link.lower():
                        continue
                    elif tipo_arquivo.lower() == "xml" and "xml" not in texto_link.lower():
                        continue
                    elif tipo_arquivo.lower() == "danfe" and "danfe" not in texto_link.lower():
                        continue
                
                # Extrair o nome do arquivo do atributo onclick
                match = re.search(r'VisualizarArquivo\("([^"]+)"\)', onclick)
                if match:
                    nome_arquivo = match.group(1)
                    print(f"Tentando baixar: {nome_arquivo}")
                    print(f"Texto do link: {texto_link}")
                    
                    # Limpar o texto do link e armazenar
                    texto_limpo = texto_link.strip()
                    self.mapeamento_arquivos[nome_arquivo] = texto_limpo
                    
                    # Também mapear com underscores caso o navegador altere o nome
                    self.mapeamento_arquivos[nome_arquivo.replace(" ", "_")] = texto_limpo
                    
                    # Rolar até o link para garantir que está visível
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                    time.sleep(0.5)  # Pequena pausa após rolagem
                    
                    # Clicar no link para iniciar o download
                    link.click()
                    
                    # Aguardar um tempo para o download iniciar
                    time.sleep(3)
                    
                    downloads_realizados += 1
                    arquivos_baixados.append(nome_arquivo)
            
            
            # Aguardar um tempo para os downloads concluírem
            if downloads_realizados > 0:
                print(f"Aguardando a conclusão de {downloads_realizados} downloads...")
                # Reduzir o tempo base para 20 segundos e somar 2 por arquivo
                tempo_espera = max(20, 2 * downloads_realizados) 
                print(f"Aguardando {tempo_espera} segundos para os downloads terminarem...")
                time.sleep(tempo_espera)
                print("Downloads concluídos")
                
                # Organizar os arquivos baixados em pastas por empresa
                self.organizar_arquivos_por_empresa(codigo_empresa)
                
                return arquivos_baixados
            else:
                print("Nenhum arquivo encontrado para download")
                return False
            
        except Exception as e:
            print(f"Erro ao baixar arquivos: {e}")
            
            # Salvar screenshot para diagnóstico
            screenshot_path = os.path.join(self.download_path, "erro_download.png")
            self.driver.save_screenshot(screenshot_path)
            print(f"Screenshot salvo em: {screenshot_path}")
            
            return False
    
    def organizar_arquivos_por_empresa(self, codigo_empresa):
        """Organiza os arquivos baixados na pasta da empresa correspondente"""
        try:
            print(f"Organizando arquivos para a empresa {codigo_empresa}...")
            
            # Listar todos os arquivos na pasta de download base
            arquivos = [f for f in os.listdir(self.download_path) if os.path.isfile(os.path.join(self.download_path, f))]
            
            # Filtrar TODOS os arquivos que contenham o código da empresa no nome
            arquivos_relevantes = [f for f in arquivos if codigo_empresa in f]
            
            print(f"Encontrados {len(arquivos_relevantes)} arquivos para organizar")
            
            # Obter a pasta de destino para esta empresa
            pasta_destino = self.pastas_empresas.get(codigo_empresa)
            if not pasta_destino:
                print(f"Pasta de destino não encontrada para o código {codigo_empresa}")
                return False
            
            # Mapeamento fixo de códigos CEMIG para garantir organização
            mapa_origens = {
                "510": "CEMIG",
                "720": "Centroeste",
                "740": "SeteLagoas"
            }

            for arquivo in arquivos_relevantes:
                caminho_origem = os.path.join(self.download_path, arquivo)
                print(f"Processando arquivo: {arquivo}")
                
                # 1. Tentar identificar pelo código numérico no nome do arquivo (Mais robusto)
                # Exemplos: F_510..., B_720..., F_740...
                subpasta_nome = ""
                for codigo, nome in mapa_origens.items():
                    if f"_{codigo}_" in arquivo or arquivo.startswith(f"F_{codigo}") or arquivo.startswith(f"B_{codigo}"):
                        subpasta_nome = nome
                        break
                
                # 2. Se não encontrou pelo código, tenta pelo texto do link (Fallback)
                if not subpasta_nome:
                    texto_link = self.mapeamento_arquivos.get(arquivo)
                    if not texto_link:
                        for key, val in self.mapeamento_arquivos.items():
                            if key.replace(" ", "_") in arquivo.replace(" ", "_") or arquivo.replace(" ", "_") in key.replace(" ", "_"):
                                texto_link = val
                                break
                    
                    if texto_link:
                        if "Centroeste" in texto_link: subpasta_nome = "Centroeste"
                        elif "SeteLagoas" in texto_link: subpasta_nome = "SeteLagoas"
                        elif "CEMIG" in texto_link: subpasta_nome = "CEMIG"
                
                # 3. Último recurso
                if not subpasta_nome:
                    subpasta_nome = "OUTROS"

                # Criar a subpasta final (CEMIG/Grupo/ONS/Origem)
                pasta_final_transmissora = os.path.join(pasta_destino, subpasta_nome)
                os.makedirs(pasta_final_transmissora, exist_ok=True)
                
                caminho_destino = os.path.join(pasta_final_transmissora, arquivo)
                
                try:
                    # Evitar sobrescrever
                    if os.path.exists(caminho_destino):
                        nome_base, extensao = os.path.splitext(arquivo)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        novo_nome = f"{nome_base}_{timestamp}{extensao}"
                        caminho_destino = os.path.join(pasta_final_transmissora, novo_nome)
                    
                    print(f"Movendo para: {subpasta_nome}/{arquivo}")
                    shutil.move(caminho_origem, caminho_destino)
                except Exception as move_error:
                    print(f"Erro ao mover {arquivo}: {move_error}")
                    try:
                        shutil.copy2(caminho_origem, caminho_destino)
                        os.remove(caminho_origem)
                    except: pass
            
            print("Organização de arquivos concluída")
            return True
            
        except Exception as e:
            print(f"Erro ao organizar arquivos: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def baixar_boletos(self, codigo_empresa):
        """Baixa os boletos encontrados na página de resultados"""
        return self.baixar_arquivos(codigo_empresa, "boleto")
    
    def baixar_xmls(self, codigo_empresa):
        """Baixa os XMLs encontrados na página de resultados"""
        return self.baixar_arquivos(codigo_empresa, "xml")
    
    def baixar_danfes(self, codigo_empresa):
        """Baixa os DANFEs encontrados na página de resultados"""
        return self.baixar_arquivos(codigo_empresa, "danfe")
    
    def fechar(self):
        """Fecha o navegador"""
        self.driver.quit()

def baixar_documentos_ae(codigos_empresas=None, download_path=None, headless=True):
    """
    Função principal para baixar documentos das empresas da AE
    
    Args:
        codigos_empresas: Lista de códigos ONS das empresas (se None, baixa todas)
        download_path: Caminho para salvar os arquivos baixados
        headless: Se True, executa o Chrome em modo headless (sem interface gráfica)
    
    Returns:
        Dicionário com resultados por empresa
    """
    # Se não especificou empresas, usar todas do empresas.json
    if codigos_empresas is None:
        resultados_totais = {}
        for empresa_mae, cod_ons_dict in EMPRESAS.items():
            print(f"\nProcessando grupo: {empresa_mae}")
            for cod_ons, nome_ons in cod_ons_dict.items():
                print(f"\n=== Processando empresa {nome_ons} (código {cod_ons}) ===\n")
                
                downloader = AEDownloader(empresa_mae, cod_ons, nome_ons, download_path, headless)
                
                try:
                    # Iniciar sessão
                    if not downloader.iniciar_sessao():
                        resultados_totais[cod_ons] = {"erro": "Falha ao iniciar sessão"}
                        continue
                    
                    # Verificar JavaScript
                    downloader.verificar_javascript()
                    
                    # Tentar até 3 vezes
                    for tentativa in range(1, 4):
                        print(f"\n=== Tentativa {tentativa} de 3 ===\n")
                        
                        # Pesquisar empresa
                        if downloader.pesquisar_empresa(cod_ons):
                            # Verificar JavaScript novamente após a pesquisa
                            downloader.verificar_javascript()
                            
                            # Aguardar um momento para garantir que a página está completamente carregada
                            print("Aguardando 5 segundos para garantir carregamento completo...")
                            time.sleep(5)
                            
                            # Baixar todos os tipos de documentos
                            arquivos = downloader.baixar_arquivos(cod_ons)
                            if arquivos:
                                print(f"Download concluído com sucesso para {nome_ons}!")
                                resultados_totais[cod_ons] = {
                                    "nome": nome_ons,
                                    "status": "sucesso",
                                    "arquivos": arquivos
                                }
                                break
                            else:
                                print(f"Falha no download na tentativa {tentativa}")
                                
                                if tentativa < 3:
                                    print("Tentando novamente...")
                                    # Recarregar a página para nova tentativa
                                    downloader.driver.get(downloader.base_url)
                                    # Aguardar mais tempo entre tentativas
                                    print(f"Aguardando 10 segundos antes da próxima tentativa...")
                                    time.sleep(10)
                                else:
                                    resultados_totais[cod_ons] = {
                                        "nome": nome_ons,
                                        "status": "falha",
                                        "mensagem": "Falha no download após 3 tentativas"
                                    }
                        else:
                            print(f"Falha na pesquisa na tentativa {tentativa}")
                            
                            if tentativa < 3:
                                print("Tentando novamente...")
                                # Recarregar a página para nova tentativa
                                downloader.driver.get(downloader.base_url)
                                # Aguardar mais tempo entre tentativas
                                print(f"Aguardando 10 segundos antes da próxima tentativa...")
                                time.sleep(10)
                            else:
                                resultados_totais[cod_ons] = {
                                    "nome": nome_ons,
                                    "status": "falha",
                                    "mensagem": "Falha na pesquisa após 3 tentativas"
                                }
                finally:
                    downloader.fechar()
        
        return resultados_totais

    # Caso uma lista específica de códigos seja passada (legado ou filtro manual)
    # Procurar os nomes nos dados carregados
    todas_empresas_achatadas = {}
    for grupo in EMPRESAS.values():
        todas_empresas_achatadas.update(grupo)
    
    resultados = {}
    
    # Processar cada empresa da lista fornecida
    for codigo in codigos_empresas:
        nome_empresa = todas_empresas_achatadas.get(codigo, f"Empresa_{codigo}")
        # Encontrar a empresa_mae para este código
        empresa_mae_encontrada = "Outros"
        for mae, sub in EMPRESAS.items():
            if codigo in sub:
                empresa_mae_encontrada = mae
                break
        
        print(f"\n=== Processando empresa {nome_empresa} (código {codigo}) ===\n")
        
        downloader = AEDownloader(empresa_mae_encontrada, codigo, nome_empresa, download_path, headless)
        
        try:
            # Iniciar sessão
            if not downloader.iniciar_sessao():
                resultados[codigo] = {"erro": "Falha ao iniciar sessão"}
                continue
            
            # Verificar JavaScript
            downloader.verificar_javascript()
            
            # Tentar até 3 vezes
            for tentativa in range(1, 4):
                print(f"\n=== Tentativa {tentativa} de 3 ===\n")
                
                # Pesquisar empresa
                if downloader.pesquisar_empresa(codigo):
                    # Verificar JavaScript novamente após a pesquisa
                    downloader.verificar_javascript()
                    
                    # Aguardar um momento para garantir que a página está completamente carregada
                    print("Aguardando 5 segundos para garantir carregamento completo...")
                    time.sleep(5)
                    
                    # Baixar todos os tipos de documentos
                    arquivos = downloader.baixar_arquivos(codigo)
                    if arquivos:
                        print(f"Download concluído com sucesso para {nome_empresa}!")
                        resultados[codigo] = {
                            "nome": nome_empresa,
                            "status": "sucesso",
                            "arquivos": arquivos
                        }
                        break
                    else:
                        print(f"Falha no download na tentativa {tentativa}")
                        
                        if tentativa < 3:
                            print("Tentando novamente...")
                            # Recarregar a página para nova tentativa
                            downloader.driver.get(downloader.base_url)
                            # Aguardar mais tempo entre tentativas
                            print(f"Aguardando 10 segundos antes da próxima tentativa...")
                            time.sleep(10)
                        else:
                            resultados[codigo] = {
                                "nome": nome_empresa,
                                "status": "falha",
                                "mensagem": "Falha no download após 3 tentativas"
                            }
                else:
                    print(f"Falha na pesquisa na tentativa {tentativa}")
                    
                    if tentativa < 3:
                        print("Tentando novamente...")
                        # Recarregar a página para nova tentativa
                        downloader.driver.get(downloader.base_url)
                        # Aguardar mais tempo entre tentativas
                        print(f"Aguardando 10 segundos antes da próxima tentativa...")
                        time.sleep(10)
                    else:
                        resultados[codigo] = {
                            "nome": nome_empresa,
                            "status": "falha",
                            "mensagem": "Falha na pesquisa após 3 tentativas"
                        }
        finally:
            downloader.fechar()
    
    return resultados

if __name__ == "__main__":
    # Exemplo de uso com modo headless
    resultados = baixar_documentos_ae(headless=True)
    
    print("\n=== Resumo dos resultados ===\n")
    for codigo, resultado in resultados.items():
        if resultado.get("status") == "sucesso":
            print(f"✅ {resultado['nome']} (código {codigo}): {len(resultado['arquivos'])} arquivos baixados")
        else:
            print(f"❌ {resultado['nome']} (código {codigo}): {resultado.get('mensagem', 'Falha desconhecida')}")