import requests
import json
import re
import os
from datetime import datetime
import time
from bs4 import BeautifulSoup

class GuairaDownloader:
    def __init__(self, empresa_mae=None, cod_ons=None, nome_ons=None):
        self.session = requests.Session()
        self.base_url = "https://faturamentoguaira.cesbe.com.br"
        self.cod_ons = cod_ons
        self.nome_ons = nome_ons
        self.empresa_mae = empresa_mae
        self.i_cod_emp = "15" # Conforme INSIGHT C#
        
        # Organização de pastas padrão
        if empresa_mae and cod_ons:
            self.download_path = os.path.join(r"C:\Users\Bruno\Downloads\TUST\GUAIRA", empresa_mae, cod_ons)
        else:
            self.download_path = r"C:\Users\Bruno\Downloads\TUST\GUAIRA\GERAL"
            
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Referer": self.base_url + "/"
        }

    def login(self):
        try:
            # Login conforme INSIGHT C#: CodOns={0}&CodEmp=15
            payload = {
                "CodOns": self.cod_ons,
                "CodEmp": self.i_cod_emp
            }
            response = self.session.post(self.base_url + "/", data=payload, headers=self.headers)
            if response.status_code == 200 and "Notas" in response.text:
                print(f"Login realizado com sucesso para {self.nome_ons} ({self.cod_ons})")
                return True
            return False
        except Exception as e:
            print(f"Erro no login: {e}")
            return False

    def get_notas(self):
        """Lista todas as notas fiscais da grade"""
        url = f"{self.base_url}/Home/Notas?iCodEmp={self.i_cod_emp}&iCodOns={self.cod_ons}"
        response = self.session.get(url, headers=self.headers)
        if response.status_code != 200: return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select("table.tableGrid tr.dif")
        
        notas = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
                data_emissao_str = cols[1].text.strip()
                # Competencia baseada no mes/ano da emissao (Padrao .NET)
                dt_emissao = datetime.strptime(data_emissao_str, "%d/%m/%Y")
                
                notas.append({
                    'numero': cols[0].text.strip(),
                    'data_emissao': dt_emissao,
                    'competencia': dt_emissao.strftime("%m/%Y"),
                    'url_danfe': self.base_url + cols[4].find('a')['href'] if cols[4].find('a') else None,
                    'url_xml': self.base_url + cols[5].find('a')['href'] if cols[5].find('a') else None
                })
        return notas

    def get_boletos(self):
        """Lista todos os boletos da grade"""
        url = f"{self.base_url}/Home/Boletos?iCodEmp={self.i_cod_emp}&iCodOns={self.cod_ons}"
        response = self.session.get(url, headers=self.headers)
        if response.status_code != 200: return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select("table.tableGrid tr.dif")
        
        boletos = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 8:
                data_vencimento_str = cols[5].text.strip()
                dt_venc = datetime.strptime(data_vencimento_str, "%d/%m/%Y")
                
                # Na Guaíra, a competência do boleto costuma bater com o mês de emissão da NF
                # O C# faz um GetCompetenciaFromDataVencimento. Vamos simplificar mes/ano.
                boletos.append({
                    'competencia': dt_venc.strftime("%m/%Y"),
                    'url_download': self.base_url + cols[7].find('a')['href'] if cols[7].find('a') else None
                })
        return boletos

    def baixar_arquivo(self, url, nome_arquivo):
        try:
            if not url: return False
            response = self.session.get(url, headers=self.headers)
            if response.status_code == 200:
                os.makedirs(self.download_path, exist_ok=True)
                path = os.path.join(self.download_path, nome_arquivo)
                with open(path, 'wb') as f:
                    f.write(response.content)
                print(f"Sucesso: {nome_arquivo}")
                return True
            return False
        except Exception as e:
            print(f"Erro ao baixar {nome_arquivo}: {e}")
            return False

def carregar_config():
    # Caminho ajustado para rodar de dentro da pasta Robots
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Data', 'empresas.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    empresas = carregar_config()
    
    for empresa_mae, cod_ons_dict in empresas.items():
        print(f"\n=== GRUPO: {empresa_mae} ===")
        for cod_ons, nome_ons in cod_ons_dict.items():
            # Filtro para não tentar rodar em tudo, mas se quiser tudo é só abrir
            # Por enquanto rodando conforme a lógica do script inicial
            if "Anemus" in nome_ons or "Guaíra" in nome_ons or True: 
                downloader = GuairaDownloader(empresa_mae, cod_ons, nome_ons)
                if downloader.login():
                    notas = downloader.get_notas()
                    boletos = downloader.get_boletos()
                    
                    if not notas:
                        print(f"Nenhuma nota encontrada para {nome_ons}")
                        continue
                    
                    # FILTRO DE RECÊNCIA: Pegar apenas o mês/ano mais recente
                    notas.sort(key=lambda x: x['data_emissao'], reverse=True)
                    mais_recente = notas[0]['data_emissao']
                    notas_filtradas = [
                        n for n in notas 
                        if n['data_emissao'].month == mais_recente.month and n['data_emissao'].year == mais_recente.year
                    ]
                        
                    print(f"Processando {len(notas_filtradas)} fatura(s) do mês mais recente ({mais_recente.strftime('%m/%Y')}) para {nome_ons}...")
                    
                    for nf in notas_filtradas:
                        comp = nf['competencia'].replace("/", "_")
                        num = nf['numero']
                        
                        # Download DANFE e XML
                        downloader.baixar_arquivo(nf['url_danfe'], f"DANFE_{num}_{comp}.pdf")
                        downloader.baixar_arquivo(nf['url_xml'], f"XML_{num}_{comp}.xml")
                        
                        # Tenta encontrar o boleto correspondente
                        boleto_match = next((b for b in boletos if b['competencia'] == nf['competencia']), None)
                        if boleto_match:
                            downloader.baixar_arquivo(boleto_match['url_download'], f"Boleto_{num}_{comp}.pdf")
                        else:
                            print(f"Boleto não encontrado para a competência {nf['competencia']}")
                            
                time.sleep(1)

if __name__ == "__main__":
    main()