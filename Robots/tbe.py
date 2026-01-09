import requests
import os
import re
import json
import time
from bs4 import BeautifulSoup

try:
    from Robots.base_robot import BaseRobot
except ImportError:
    from base_robot import BaseRobot

class TBERobot(BaseRobot):
    """
    Robô para Portal TBE (TB Energia).
    URL: https://portalcliente.tbenergia.com.br/
    Autenticação: Usuário e Senha obrigatórios.
    """

    # Mapeamento fixo de CNPJs e siglas das transmissoras conhecidas (Copiado do original)
    TRANSMISSORAS = {
        "03984987000114": {"sigla": "ECTE", "nome": "ECTE"},
        "04416923000260": {"sigla": "ETEP", "nome": "ETEP"},
        "04416935000295": {"sigla": "EATE", "nome": "EATE"},
        "04416935000376": {"sigla": "EATE", "nome": "EATE"},
        "05321920000206": {"sigla": "ERTE", "nome": "ERTE"},
        "05321987000321": {"sigla": "ENTE", "nome": "ENTE"},
        "05321987000240": {"sigla": "ENTE", "nome": "ENTE"},
        "05973734000170": {"sigla": "LUMITRANS", "nome": "LUMITRANS"},
        "07752818000100": {"sigla": "STC", "nome": "STC"},
        "10319371000275": {"sigla": "EBTE", "nome": "EBTE"},
        "11004138000266": {"sigla": "ESDE", "nome": "ESDE"},
        "14929924000262": {"sigla": "ETSE", "nome": "ETSE"},
        "24870962000240": {"sigla": "EDTE", "nome": "EDTE"},
        "26643937000250": {"sigla": "ESTE", "nome": "ESTE"},
        "26643937000330": {"sigla": "ESTE", "nome": "ESTE"},
    }

    # Simplificado para busca parcial
    CNPJ_BASE_MAP = {
        "03984987": "ECTE", "04416923": "ETEP", "04416935": "EATE",
        "05321920": "ERTE", "05321987": "ENTE", "05973734": "LUMITRANS",
        "07752818": "STC", "10319371": "EBTE", "11004138": "ESDE",
        "14929924": "ETSE", "24870962": "EDTE", "26643937": "ESTE",
    }

    def __init__(self):
        super().__init__("tbe")
        self.base_url = "https://portalcliente.tbenergia.com.br"
        self.session = requests.Session()
        self.session.headers.update({
             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def sanitize_name(self, name):
         if not name: return "DESCONHECIDO"
         clean = re.sub(r'[<>:"/\\|?*]', '_', str(name))
         return " ".join(clean.split()).strip()

    def get_transmissora_sigla(self, cnpj, nome_empresa):
        # Tenta match exato
        if cnpj in self.TRANSMISSORAS: return self.TRANSMISSORAS[cnpj]['sigla']
        
        # Tenta match base (8 digitos)
        cnpj_base = cnpj[:8]
        if cnpj_base in self.CNPJ_BASE_MAP: return self.CNPJ_BASE_MAP[cnpj_base]
        
        # Fallback: Nome sanitizado
        return self.sanitize_name(nome_empresa[:10].upper())

    def login(self, user, password):
        try:
            self.session.get(f"{self.base_url}/")
            data = {'Login': user, 'Senha': password}
            resp = self.session.post(f"{self.base_url}/Login/Index", data=data)
            if "Fechamento" in resp.url or resp.status_code == 200: 
                # Algumas vezes nao redireciona mas loga? Verificar cookie ou conteudo
                return True
        except Exception as e:
            self.logger.error(f"Erro Login: {e}")
        return False

    def baixar_arquivo(self, url, path, tipo):
        try:
            if not url.startswith('http'):
                url = f"{self.base_url}{url}"
            resp = self.session.get(url)
            if resp.status_code == 200:
                with open(path, 'wb') as f:
                    f.write(resp.content)
                self.logger.info(f"Salvo {tipo}: {os.path.basename(path)}")
                return True
        except Exception as e:
            self.logger.error(f"Erro ao baixar {tipo}: {e}")
        return False

    def run(self):
        user = self.args.user
        password = self.args.password
        agente = self.args.agente  # Pode ser CNPJ ou Cod ONS

        if not user or not password:
            self.logger.error("Usuário e Senha são obrigatórios para TBE.")
            return
        
        if not agente:
            self.logger.error("Agente (CNPJ) obrigatório.")
            return

        self.logger.info(f"Iniciando TBE para Agente {agente}...")

        if not self.login(user, password):
            self.logger.error("Falha no Login TBE. Verifique credenciais.")
            return

        self.logger.info("Login realizado. Buscando notas...")
        
        try:
            url_notas = f"{self.base_url}/Fechamento/NotasRecentes?CNPJ={agente}"
            resp = self.session.get(url_notas)
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table', {'id': 'NfRecentes'})
            
            if not table or not table.find('tbody'):
                self.logger.warning("Nenhuma tabela de notas encontrada.")
                return

            rows = table.find('tbody').find_all('tr')
            self.logger.info(f"Encontradas {len(rows)} linhas na tabela.")

            base_path = self.get_output_path()
            out_root = os.path.join(base_path, str(agente))
            os.makedirs(out_root, exist_ok=True)

            processed = 0
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 7: continue
                
                # Extração
                competencia = cells[0].text.strip()
                nf_num = cells[1].text.strip()
                empresa_nome = cells[3].text.strip()
                cnpj_full = ''.join(filter(str.isdigit, cells[4].text))
                
                # Links
                xml_link = None
                pdf_link = None
                for a in cells[-1].find_all('a'):
                    txt = (a.text or '').upper()
                    if 'XML' in txt: xml_link = a.get('href')
                    elif 'PDF' in txt or 'DANFE' in txt: pdf_link = a.get('href')

                if xml_link:
                    # Identificar Transmissora
                    sigla = self.get_transmissora_sigla(cnpj_full, empresa_nome)
                    
                    # Output Path
                    trans_dir = os.path.join(out_root, self.sanitize_name(sigla))
                    os.makedirs(trans_dir, exist_ok=True)
                    
                    comp_clean = self.sanitize_name(competencia)
                    base_name = f"{sigla}_NF_{nf_num}_{comp_clean}"
                    
                    # Baixar XML
                    if self.baixar_arquivo(xml_link, os.path.join(trans_dir, f"{base_name}.xml"), "XML"):
                        processed += 1
                    
                    # Baixar PDF
                    target_pdf_link = pdf_link or xml_link.replace('DownloadXml', 'DownloadPdf')
                    self.baixar_arquivo(target_pdf_link, os.path.join(trans_dir, f"{base_name}.pdf"), "PDF")

            self.logger.info(f"Processamento concluído. {processed} notas processadas.")

        except Exception as e:
            self.logger.error(f"Erro durante execução TBE: {e}")

if __name__ == "__main__":
    robot = TBERobot()
    robot.run()
