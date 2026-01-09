import requests
import re
import os
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin

try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

class AluparBaseRobot(BaseRobot):
    """
    Classe Base para Robôs do Grupo Alupar.
    URL Base: https://faturas.alupar.com.br:8090
    """

    def __init__(self, name, company_id, btn_text="Entrar"):
        super().__init__(name)
        self.robot_alias = name 
        self.base_url = "https://faturas.alupar.com.br:8090"
        self.company_id = str(company_id)
        self.btn_text = btn_text
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://tecpenergia.com.br/" 
        }

    def _parse_data(self, data_str):
        try:
            return datetime.strptime(data_str, '%d/%m/%Y')
        except: return None

    def obter_faturas(self, cod_ons):
        """Busca faturas via POST /Fatura/Emissao/{ID}"""
        url = f"{self.base_url}/Fatura/Emissao/{self.company_id}"
        data = {
            "Codigo": cod_ons,
            "btnEntrar": self.btn_text
        }
        
        try:
            resp = self.session.post(url, data=data, headers=self.headers)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            tabela = soup.find('table', class_=lambda x: x and 'table-bordered' in x)
            if not tabela: tabela = soup.find('table')
            
            faturas = []
            if tabela:
                rows = tabela.select('tbody tr')
                for row in rows:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) >= 8:
                        dt_str = cols[6].text.strip()
                        dt = self._parse_data(dt_str)
                        if not dt: continue
                        
                        faturas.append({
                            'numero_nf': cols[5].text.strip(),
                            'data_emissao': dt,
                            'transmissora': cols[1].text.strip(),
                            'links_element': cols[-1]
                        })
            return faturas
        except Exception as e:
            self.logger.error(f"Erro ao buscar faturas: {e}")
            return []

    def extrair_links(self, td_element):
        links = []
        acoes = td_element.find_all('a')
        for acao in acoes:
            onclick = acao.get('onclick', '')
            title = acao.get('title', '').upper()
            
            match = re.search(r"window\.open\('([^']+)'", onclick)
            if match:
                rel_url = match.group(1)
                full_url = urljoin(self.base_url, rel_url)
                tipo = 'XML' if 'XML' in title else 'DANFE'
                links.append({'tipo': tipo, 'url': full_url})
        return links

    def obter_boleto(self, cod_ons):
        """Busca boleto recente via GET /Home/Boletos"""
        url = f"{self.base_url}/Home/Boletos?iCodEmp={self.company_id}&iCodOns={cod_ons}"
        try:
            resp = self.session.get(url, headers=self.headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                tabela = soup.find('table', {'class': 'tableGrid'})
                if tabela:
                    linha = tabela.find('tr', {'class': 'dif'})
                    if linha:
                        link = linha.find('a', href=True)
                        if link: return urljoin(self.base_url, link['href'])
        except: pass
        return None

    def baixar_arquivo(self, url, path):
        try:
            r = self.session.get(url, headers=self.headers, stream=True)
            r.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in r.iter_content(8192): f.write(chunk)
            self.logger.info(f"Salvo: {os.path.basename(path)}")
        except Exception as e:
            self.logger.error(f"Erro download {os.path.basename(path)}: {e}")

    def run(self):
        cod_ons = self.args.agente
        if not cod_ons:
            self.logger.error("Código ONS obrigatório (--agente).")
            return

        competencia_str = self.args.competencia
        target_mes = int(competencia_str[4:6]) if competencia_str else None
        target_ano = int(competencia_str[:4]) if competencia_str else None

        self.logger.info(f"Iniciando {self.robot_alias.upper()} (ID {self.company_id}) para ONS {cod_ons}...")

        # 1. Buscar
        todas = self.obter_faturas(cod_ons)
        
        # 2. Filtrar
        filtradas = []
        if todas:
            if target_mes:
                filtradas = [f for f in todas if f['data_emissao'].month == target_mes and f['data_emissao'].year == target_ano]
            else:
                max_dt = max([f['data_emissao'] for f in todas])
                filtradas = [f for f in todas if f['data_emissao'] == max_dt]
                self.logger.info(f"Competência automática (Mais Recente): {max_dt.strftime('%m/%Y')}")

        if not filtradas:
            self.logger.warning("Nenhuma fatura encontrada.")
        else:
            self.logger.info(f"Baixando {len(filtradas)} faturas...")

        # 3. Baixar
        base_path = self.get_output_path()
        out_dir = os.path.join(base_path, str(cod_ons))
        os.makedirs(out_dir, exist_ok=True)

        for f in filtradas:
            links = self.extrair_links(f['links_element'])
            num = f['numero_nf']
            dt_s = f['data_emissao'].strftime("%Y%m%d")
            t_nome = re.sub(r'[^\w\s-]', '', f['transmissora']).strip()
            
            # Sanitizar nome da transmissora para evitar erro de caminho
            t_nome = re.sub(r'[<>:"/\\|?*]', '', t_nome)

            t_dir = os.path.join(out_dir, t_nome)
            os.makedirs(t_dir, exist_ok=True)

            for link in links:
                ext = ".xml" if link['tipo'] == 'XML' else ".pdf"
                nome = f"{link['tipo']}_{cod_ons}_{num}_{dt_s}{ext}"
                self.baixar_arquivo(link['url'], os.path.join(t_dir, nome))

        # 4. Boleto
        url_bol = self.obter_boleto(cod_ons)
        if url_bol:
            nome_bol = f"BOLETO_{cod_ons}_{datetime.now().strftime('%Y%m%d')}.pdf"
            self.baixar_arquivo(url_bol, os.path.join(out_dir, nome_bol))
