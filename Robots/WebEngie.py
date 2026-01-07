import os
import time
import json
import re
import datetime
import base64
import requests
from urllib.parse import quote

# Configurações
from utils_paths import get_base_download_path, ensure_dir
BASE_DIR_DEFAULT = get_base_download_path("WEBENGIE")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Data")
EMPRESAS_JSON_PATH = os.path.join(DATA_DIR, "empresas.json")

# Valores de Fallback (Extraídos do robô legado C#)
FALLBACK_FWUID = "ZDROWDdLOGtXcTZqSWZiU19ZaDJFdzk4bkk0bVJhZGJCWE9mUC1IZXZRbmcyNDguMTAuNS01LjAuMTA"
FALLBACK_LOADED = {
    "APPLICATION@markup://siteforce:communityApp": "k6JknytX-C_r-3PiqoI3OQ",
    "COMPONENT@markup://instrumentation:o11ySecondaryLoader": "NAR59T88qTprOlgZG3yLoQ"
}
URL_BASE = "https://engiebrasil.my.site.com/portaltransmissora/s/"
URL_AURA = "https://engiebrasil.my.site.com/portaltransmissora/s/sfsites/aura"

def sanitize_name(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

class EngieRobot:
    def __init__(self, ons_code, ons_name, output_dir=None):
        self.ons_code = ons_code
        self.ons_name = ons_name
        self.ons_name = ons_name
        self.output_path = os.path.join(output_dir or BASE_DIR_DEFAULT, self.ons_name)
        ensure_dir(self.output_path)
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        })
        self.aura_context = {}
        self.fwuid = ""
        self.request_id = 1
        self.action_id = 100 

    def initialize_session(self):
        """Inicializa sessão via Requests e extrai FWUID do HTML."""
        print("    [API] Inicializando conexão HTTP...")
        try:
            r = self.session.get(URL_BASE, timeout=30)
            if r.status_code != 200:
                print(f"    [ERRO] Falha ao acessar página inicial: {r.status_code}")
                return False
            
            # Tenta extrair fwuid do HTML
            src = r.text
            match = re.search(r'["\']fwuid["\']\s*:\s*["\']([^"\']+)["\']', src)
            
            if match:
                self.fwuid = match.group(1)
                print(f"    [OK] fwuid extraído dinamicamente: {self.fwuid[:10]}...")
            else:
                self.fwuid = FALLBACK_FWUID
                print(f"    [AVISO] fwuid não encontrado no HTML. Usando FALLBACK: {self.fwuid[:10]}...")

            # Monta o contexto
            self.aura_context = {
                "mode": "PROD",
                "fwuid": self.fwuid,
                "app": "siteforce:communityApp",
                "loaded": FALLBACK_LOADED, # Usamos o loaded fixo pois é difícil extrair via regex confiável
                "dn": [],
                "globals": {},
                "uad": False
            }
            return True
        except Exception as e:
            print(f"    [ERRO] Exceção na inicialização: {e}")
            return False

    def call_aura(self, descriptor, params, extra_key=""):
        url = f"{URL_AURA}?r={self.request_id}"
        if extra_key:
            url += f"&{extra_key}=1"
        
        message = {
            "actions": [
                {
                    "id": f"{self.action_id};a",
                    "descriptor": descriptor,
                    "callingDescriptor": "markup://c:PortaltransmissoraTab",
                    "params": params
                }
            ]
        }
        
        payload = {
            "message": json.dumps(message),
            "aura.context": json.dumps(self.aura_context),
            "aura.pageURI": "/portaltransmissora/s/",
            "aura.token": "null"
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": URL_BASE,
            "Origin": "https://engiebrasil.my.site.com"
        }
        
        # Encodar payload manualmente
        data_str = "&".join([f"{k}={quote(v)}" for k, v in payload.items()])
        
        try:
            r = self.session.post(url, data=data_str, headers=headers, timeout=60)
            self.request_id += 1
            self.action_id += 1
            
            if r.status_code == 200:
                # O retorno geralmente começa com */ e um json
                text = r.text
                if text.startswith("*/"):
                    text = text[2:] # Remove o prefixo de segurança do Aura
                
                try:
                    resp_json = json.loads(text)
                except:
                    print(f"    [ERRO] Falha ao decodificar JSON: {text[:100]}...")
                    return None

                # Verificar se o framework foi atualizado
                if "exceptionEvent" in resp_json and resp_json.get("exceptionEvent") == True:
                     # Tenta pegar fwuid novo da mensagem de erro se houver "Expected: ..."
                     # Mas por simplicidade, vamos apenas logar.
                     print(f"    [ERRO] Exceção Aura: {resp_json}")
                     return None

                actions = resp_json.get('actions', [])
                if actions:
                    act = actions[0]
                    state = act.get('state')
                    if state == 'SUCCESS':
                        return act.get('returnValue')
                    elif state == 'ERROR':
                         errs = act.get('error', [])
                         msg = errs[0].get('message') if errs else "Erro desconhecido"
                         print(f"    [API ERRO] {msg}")
                    else:
                        print(f"    [API ERRO] Estado: {state}")
                else:
                    print(f"    [ERRO] Resposta sem actions: {text[:100]}")
            else:
                print(f"    [ERRO] HTTP {r.status_code}")
        except Exception as e:
            print(f"    [ERRO] na requisição: {e}")
        return None

    def processar(self):
        print(f"\n>>> [ENGIE] ONS: {self.ons_code} ({self.ons_name})")
        if not self.initialize_session(): return
        
        # Competência: mês seguinte ao atual (C# usa AddMonths(1))
        # O Robô C# usa: DateTime dataBusca = GetUltimaCompetencia().AddMonths(1);
        # Vamos assumir Mês Atual + 1 para ficar igual ao C# ou Hoje?
        # O C# usa AddMonths(1), então se estamos em Janeiro, ele busca Fevereiro (vencimento).
        today = datetime.date.today()
        proximo_mes = today.replace(day=28) + datetime.timedelta(days=4)
        data_busca = proximo_mes.replace(day=1).strftime("%Y-%m-%d")
        
        # Ajuste: Algumas faturas podem estar no mês atual. O usuário pode querer configurar.
        # Por padrão vou usar o mês ATUAL, pois AddMonths(1) NO C# dependia da "UltimaCompetencia" do banco, que podia estar atrasada.
        # Vou usar data de HOJE (dia 1 do mês atual).
        data_busca = today.replace(day=1).strftime("%Y-%m-%d")
        
        print(f"    - Buscando faturas (Ref: {data_busca})...")
        
        # Tenta buscar. Se falhar, tenta mês seguinte também? O C# só tentava uma vez com base na competência.
        faturas = self.call_aura(
            "apex://PortalTransmissoraTabLController/ACTION$getInvoiceList",
            {"ONSCode": int(self.ons_code), "selectDate": data_busca},
            "other.PortalTransmissoraTabL.getInvoiceList"
        )
        
        if not faturas or len(faturas) == 0:
            print(f"    [AVISO] Nenhuma fatura encontrada. Tentando mês seguinte...")
            # Tenta mês seguinte
            data_busca_next = proximo_mes.replace(day=1).strftime("%Y-%m-%d")
            faturas = self.call_aura(
                "apex://PortalTransmissoraTabLController/ACTION$getInvoiceList",
                {"ONSCode": int(self.ons_code), "selectDate": data_busca_next},
                "other.PortalTransmissoraTabL.getInvoiceList"
            )

        if not faturas:
            print(f"    [AVISO] Nenhuma fatura encontrada para {self.ons_code} (nem atual nem próximo mês).")
            return

        print(f"    [OK] {len(faturas)} faturas recebidas.")

        for f in faturas:
            empresa = f.get('BillFromName__c', 'Empresa')
            invoice_key = f.get('InvoiceKey__c')
            instalment_id = f.get('FirstInstalmentId__c')
            vencimento = f.get('FirstInstalmentDueDate__c', '')
            
            print(f"\n      [processando] {empresa} (Venc: {vencimento})")
            
            # Sanitizar nome da empresa + ONS code para pasta única
            # Ex: EMC_9999_Nome_Empresa
            folder_name = f"EMC_{self.ons_code}_{sanitize_name(empresa)}"
            path_trans = os.path.join(self.output_path, folder_name)
            if not os.path.exists(path_trans):
                os.makedirs(path_trans, exist_ok=True)

            # Boleto
            if instalment_id:
                self.baixar(invoice_key, "BOLETO", "apex://PortalTransmissoraTabLController/ACTION$downloadBillet", 
                           {"invoiceKey": invoice_key, "instalmentId": instalment_id}, "other.PortalTransmissoraTabL.downloadBillet", path_trans)
            
            # DANFE
            self.baixar(invoice_key, "DANFE", "apex://PortalTransmissoraTabLController/ACTION$downloadInvoicePDF", 
                       {"NFe": invoice_key}, "other.PortalTransmissoraTabL.downloadInvoicePDF", path_trans)
            
            # XML
            self.baixar(invoice_key, "XML", "apex://PortalTransmissoraTabLController/ACTION$downloadInvoiceXML", 
                       {"NFe": invoice_key}, "other.PortalTransmissoraTabL.downloadInvoiceXML", path_trans)

    def baixar(self, key, tipo, descriptor, params, extra_key, save_folder):
        print(f"        -> {tipo}...")
        res_b64 = self.call_aura(descriptor, params, extra_key)
        
        if res_b64:
            ext = ".xml" if tipo == "XML" else ".pdf"
            # Nome do arquivo padronizado
            filename = f"{tipo}_{self.ons_code}_{datetime.datetime.now().strftime('%Y%m%d')}_{key}{ext}"
            target = os.path.join(save_folder, filename)
            
            try:
                # C# verifica Convert.FromBase64String. 
                # O retorno pode ser XML puro (se startar com <) ou Base64.
                # O C# assume Base64 sempre no código que vi. Mas vamos garantir.
                
                # Limpeza simples de espaços/newlines que as vezes vem no base64
                res_b64_clean = res_b64.replace('\n', '').replace('\r', '').strip()
                
                try:
                    content = base64.b64decode(res_b64_clean)
                except:
                    # Se falhar decode, assume que é texto plano (ex: XML não codificado)
                    content = res_b64.encode('utf-8')
                    
                with open(target, 'wb') as file:
                    file.write(content)
                print(f"           [OK] Salvo!")
            except Exception as e:
                print(f"           [ERRO] ao salvar {tipo}: {e}")
        else:
            print(f"           [AVISO] {tipo} pendente/erro.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="WebEngie Robot")
    parser.add_argument("--empresa", type=str, help="Filtro de Empresa (AETE, etc)")
    parser.add_argument("--agente", type=str, help="Filtro de Agente (Código ONS)")
    parser.add_argument("--user", type=str, help="User (Ignorado por enquanto)")
    parser.add_argument("--password", type=str, help="Pass (Ignorado por enquanto)")
    parser.add_argument("--output_dir", help="Pasta de destino dos downloads")
    
    args = parser.parse_args()

    # Carrega config
    try:
        with open(EMPRESAS_JSON_PATH, 'r') as f:
            full_config = json.load(f)
    except:
        full_config = {}

    targets = {}
    
    if args.empresa:
        if args.empresa in full_config:
            targets = full_config[args.empresa]
        else:
            print(f"Empresa '{args.empresa}' não encontrada no JSON.")
    else:
        # Padrão: AETE
        targets = full_config.get("AETE", {})

    if args.agente:
        found = False
        # Verifica se o agente está dentro do target atual
        if args.agente in targets:
            targets = {args.agente: targets[args.agente]}
            found = True
        else:
            # Se não, procura em tudo
            for grp, items in full_config.items():
                if args.agente in items:
                    targets = {args.agente: items[args.agente]}
                    found = True
                    break
        if not found:
            print(f"Agente {args.agente} não encontrado.")
            targets = {}
    
    print(f"Iniciando WebEngie para {len(targets)} alvos...")
    
    for ons_code, ons_name in targets.items():
        bot = EngieRobot(ons_code, ons_name, output_dir=args.output_dir)
        bot.processar()
