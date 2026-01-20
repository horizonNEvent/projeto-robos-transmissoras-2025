from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
import os
import shutil
from sqlalchemy.orm import Session
from typing import Optional
import threading

from .. import database

from ..database import get_db

from .. import models, database
import json

router = APIRouter(tags=["robots"])

# Caminhos
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def get_download_path(robot_key: str):
    """Retorna o caminho de download baseado no ROOT_DIR para garantir compatibilidade Docker/Linux/Windows"""
    # Se houver uma variável de ambiente TUST_DOWNLOADS_BASE, usamos ela como base.
    # Caso contrário, usamos a pasta 'downloads' na raiz do projeto.
    base = os.environ.get("TUST_DOWNLOADS_BASE", os.path.join(ROOT_DIR, "downloads"))
    return os.path.join(base, "TUST", robot_key.upper())

ROBOTS_CONFIG = {
    "siget": {
        "script": os.path.join(ROOT_DIR, "Robots", "siget.py"),
        "download_dir": get_download_path("siget"),
        "name": "WebSiget"
    },
    "cnt": {
        "script": os.path.join(ROOT_DIR, "Robots", "cnt.py"),
        "download_dir": get_download_path("cnt"),
        "name": "WebCnt"
    },
    "pantanal": {
        "script": os.path.join(ROOT_DIR, "Robots", "pantanal.py"),
        "download_dir": get_download_path("pantanal"),
        "name": "WebPantanal"
    },
    "assu": {
        "script": os.path.join(ROOT_DIR, "Robots", "assu.py"),
        "download_dir": get_download_path("assu"),
        "name": "WebAssu"
    },
    "tropicalia": {
        "script": os.path.join(ROOT_DIR, "Robots", "tropicalia.py"),
        "download_dir": get_download_path("tropicalia"),
        "name": "WebTropicalia"
    },
    "firminopolis": {
        "script": os.path.join(ROOT_DIR, "Robots", "firminopolis.py"),
        "download_dir": get_download_path("firminopolis"),
        "name": "WebFirminopolis"
    },
    "evoltz": {
        "script": os.path.join(ROOT_DIR, "Robots", "evoltz.py"),
        "download_dir": get_download_path("evoltz"),
        "name": "WebEvoltz"
    },
    "guaira": {
        "script": os.path.join(ROOT_DIR, "Robots", "guaira.py"),
        "download_dir": get_download_path("guaira"),
        "name": "WebGuaira"
    },
    "itamaraca": {
        "script": os.path.join(ROOT_DIR, "Robots", "itamaraca.py"),
        "download_dir": get_download_path("itamaraca"),
        "name": "WebItamaraca"
    },
    "colinas": {
        "script": os.path.join(ROOT_DIR, "Robots", "colinas.py"),
        "download_dir": get_download_path("colinas"),
        "name": "WebColinas"
    },
    "simoes": {
        "script": os.path.join(ROOT_DIR, "Robots", "simoes.py"),
        "download_dir": get_download_path("simoes"),
        "name": "WebSimoes"
    },
    "fs": {
        "script": os.path.join(ROOT_DIR, "Robots", "fs.py"),
        "download_dir": get_download_path("fs"),
        "name": "WebFS"
    },
    "vineyards": {
        "script": os.path.join(ROOT_DIR, "Robots", "vineyards.py"),
        "download_dir": get_download_path("vineyards"),
        "name": "WebVineyards"
    },
    "agua_vermelha": {
        "script": os.path.join(ROOT_DIR, "Robots", "agua_vermelha.py"),
        "download_dir": get_download_path("aguavermelha"),
        "name": "WebAguaVermelha"
    },
    "webieriachogrande": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIERIACHOGRANDE.py"),
        "download_dir": get_download_path("WebIERIACHOGRANDE"),
        "name": "WebIERIACHOGRANDE"
    },
    "webiecteep": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIECTEEP.py"),
        "download_dir": get_download_path("WebIECTEEP"),
        "name": "WebIECTEEP"
    },
    "webieaguapei": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEAGUAPEI.py"),
        "download_dir": get_download_path("WebIEAGUAPEI"),
        "name": "WebIEAGUAPEI"
    },
    "webiebiguacu": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEBIGUACU.py"),
        "download_dir": get_download_path("WebIEBIGUACU"),
        "name": "WebIEBIGUACU"
    },
    "webiegaranhuns": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEGARANHUNS.py"),
        "download_dir": get_download_path("WebIEGARANHUNS"),
        "name": "WebIEGARANHUNS"
    },
    "webieitapura": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEITAPURA.py"),
        "download_dir": get_download_path("WebIEITAPURA"),
        "name": "WebIEITAPURA"
    },
    "webieitaquere": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEITAQUERE.py"),
        "download_dir": get_download_path("WebIEITAQUERE"),
        "name": "WebIEITAQUERE"
    },
    "webieitaunas": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEITAUNAS.py"),
        "download_dir": get_download_path("WebIEITAUNAS"),
        "name": "WebIEITAUNAS"
    },
    "webieivai": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEIVAI.py"),
        "download_dir": get_download_path("WebIEIVAI"),
        "name": "WebIEIVAI"
    },
    "webiejaguar6": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEJAGUAR6.py"),
        "download_dir": get_download_path("WebIEJAGUAR6"),
        "name": "WebIEJAGUAR6"
    },
    "webiejaguar8": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEJAGUAR8.py"),
        "download_dir": get_download_path("WebIEJAGUAR8"),
        "name": "WebIEJAGUAR8"
    },
    "webiejaguar9": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEJAGUAR9.py"),
        "download_dir": get_download_path("WebIEJAGUAR9"),
        "name": "WebIEJAGUAR9"
    },
    "webiemadeira": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEMADEIRA.py"),
        "download_dir": get_download_path("WebIEMADEIRA"),
        "name": "WebIEMADEIRA"
    },
    "webiemg": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEMG.py"),
        "download_dir": get_download_path("WebIEMG"),
        "name": "WebIEMG"
    },
    "webienne": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIENNE.py"),
        "download_dir": get_download_path("WebIENNE"),
        "name": "WebIENNE"
    },
    "webiepinheiros": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEPINHEIROS.py"),
        "download_dir": get_download_path("WebIEPINHEIROS"),
        "name": "WebIEPINHEIROS"
    },
    "webieserradojapi": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIESERRADOJAPI.py"),
        "download_dir": get_download_path("WebIESERRADOJAPI"),
        "name": "WebIESERRADOJAPI"
    },
    "webiesul": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIESUL.py"),
        "download_dir": get_download_path("WebIESUL"),
        "name": "WebIESUL"
    },
    "webietibagi": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIETIBAGI.py"),
        "download_dir": get_download_path("WebIETIBAGI"),
        "name": "WebIETIBAGI"
    },
    "webengie": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebEngie.py"),
        "download_dir": get_download_path("WebEngie"),
        "name": "WebEngie"
    },
    "webettm": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebETTM.py"),
        "download_dir": get_download_path("WebETTM"),
        "name": "WebETTM"
    },
    "websigetpublic": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebSigetPublic.py"),
        "download_dir": get_download_path("WebSigetPublic"),
        "name": "WebSigetPublic"
    },
    "webtaesa": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebTaesa.py"),
        "download_dir": get_download_path("WebTaesa"),
        "name": "WebTaesa"
    },
    "celeo": {
        "script": os.path.join(ROOT_DIR, "Robots", "celeo.py"),
        "download_dir": get_download_path("celeo"),
        "name": "WebCeleo"
    },
    "web_ie": {
        "script": os.path.join(ROOT_DIR, "Robots", "web_ie.py"),
        "download_dir": get_download_path("WebIE"),
        "name": "WebIE"
    },
    "arteon": {
        "script": os.path.join(ROOT_DIR, "Robots", "arteon.py"),
        "download_dir": get_download_path("ARTEON"),
        "name": "WebArteon"
    },
    "light": {
        "script": os.path.join(ROOT_DIR, "Robots", "light.py"),
        "download_dir": get_download_path("LIGHT"),
        "name": "WebLight"
    },
    "equatorial": {
        "script": os.path.join(ROOT_DIR, "Robots", "equatorial.py"),
        "download_dir": get_download_path("EQUATORIAL"),
        "name": "WebEquatorial"
    },
    "equatorial_v2": {
        "script": os.path.join(ROOT_DIR, "Robots", "equatorial_v2.py"),
        "download_dir": get_download_path("EQUATORIAL"),
        "name": "WebEquatorialV2"
    },
    "rialmas": {
        "script": os.path.join(ROOT_DIR, "Robots", "rialmas.py"),
        "download_dir": get_download_path("RIALMAS"),
        "name": "WebRialmas"
    },
    "cpfl": {
        "script": os.path.join(ROOT_DIR, "Robots", "cpfl.py"),
        "download_dir": get_download_path("CPFL"),
        "name": "WebCPFL"
    },
    "glorian": {
        "script": os.path.join(ROOT_DIR, "Robots", "glorian.py"),
        "download_dir": get_download_path("GLORIAN"),
        "name": "WebGlorian"
    },
    "copel": {
        "script": os.path.join(ROOT_DIR, "Robots", "copel.py"),
        "download_dir": get_download_path("COPEL"),
        "name": "WebCopel"
    },
    "mge": {
        "script": os.path.join(ROOT_DIR, "Robots", "mge.py"),
        "download_dir": get_download_path("MGE"),
        "name": "WebMGE"
    },
    "stategrid": {
        "script": os.path.join(ROOT_DIR, "Robots", "stategrid.py"),
        "download_dir": get_download_path("STATEGRID"),
        "name": "WebStateGrid"
    },
    "stn": {
        "script": os.path.join(ROOT_DIR, "Robots", "stn.py"),
        "download_dir": get_download_path("STN"),
        "name": "WebSTN"
    },
    "webtaesa": {
        "script": os.path.join(ROOT_DIR, "Robots", "taesa.py"),
        "download_dir": get_download_path("TAESA"),
        "name": "WebTaesa"
    },
    "tecp": {
        "script": os.path.join(ROOT_DIR, "Robots", "tecp.py"),
        "download_dir": get_download_path("TECP"),
        "name": "WebTECP"
    },
    # Alupar Group
    "elte": {"script": os.path.join(ROOT_DIR, "Robots", "elte.py"), "download_dir": get_download_path("ELTE"), "name": "WebELTE"},
    "etes": {"script": os.path.join(ROOT_DIR, "Robots", "etes.py"), "download_dir": get_download_path("ETES"), "name": "WebETES"},
    "tme": {"script": os.path.join(ROOT_DIR, "Robots", "tme.py"), "download_dir": get_download_path("TME"), "name": "WebTME"},
    "etem": {"script": os.path.join(ROOT_DIR, "Robots", "etem.py"), "download_dir": get_download_path("ETEM"), "name": "WebETEM"},
    "etvg": {"script": os.path.join(ROOT_DIR, "Robots", "etvg.py"), "download_dir": get_download_path("ETVG"), "name": "WebETVG"},
    "tne": {"script": os.path.join(ROOT_DIR, "Robots", "tne.py"), "download_dir": get_download_path("TNE"), "name": "WebTNE"},
    "etc": {"script": os.path.join(ROOT_DIR, "Robots", "etc.py"), "download_dir": get_download_path("ETC"), "name": "WebETC"},
    "etap": {"script": os.path.join(ROOT_DIR, "Robots", "etap.py"), "download_dir": get_download_path("ETAP"), "name": "WebETAP"},
    "tcc": {"script": os.path.join(ROOT_DIR, "Robots", "tcc.py"), "download_dir": get_download_path("TCC"), "name": "WebTCC"},
    "tpe": {"script": os.path.join(ROOT_DIR, "Robots", "tpe.py"), "download_dir": get_download_path("TPE"), "name": "WebTPE"},
    "tsm": {"script": os.path.join(ROOT_DIR, "Robots", "tsm.py"), "download_dir": get_download_path("TSM"), "name": "WebTSM"},
    "etb": {"script": os.path.join(ROOT_DIR, "Robots", "etb.py"), "download_dir": get_download_path("ETB"), "name": "WebETB"},
    "amazonia": {"script": os.path.join(ROOT_DIR, "Robots", "amazonia.py"), "download_dir": get_download_path("AMAZONIA"), "name": "WebAmazonia"},
    "tcpe": {"script": os.path.join(ROOT_DIR, "Robots", "tcpe.py"), "download_dir": get_download_path("TCPE"), "name": "WebTCPE"},
    "vsb": {
        "script": os.path.join(ROOT_DIR, "Robots", "vsb.py"),
        "download_dir": get_download_path("VSB"),
        "name": "WebVSB"
    },
    "verene": {
        "script": os.path.join(ROOT_DIR, "Robots", "verene.py"),
        "download_dir": get_download_path("VERENE"),
        "name": "WebVerene"
    },
    "tbe": {
        "script": os.path.join(ROOT_DIR, "Robots", "tbe.py"),
        "download_dir": get_download_path("TBE"),
        "name": "WebTBE"
    },
    "ons": {
        "script": os.path.join(ROOT_DIR, "Robots", "ons.py"),
        "download_dir": get_download_path("ONS"),
        "name": "WebOns"
    },
    "harpix": {
        "script": os.path.join(ROOT_DIR, "Robots", "harpix.py"),
        "download_dir": get_download_path("HARPIX"),
        "name": "WebHarpix"
    }
}

# Estado global: { robot_name: { set_of_active_process_ids } }
ROBOT_STATUS = {}
STATUS_LOCK = threading.Lock()

class RobotRequest(BaseModel):
    robot_name: str
    base: str | None = None
    email: str | None = None
    empresa: Optional[str] = None
    agente: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    competencia: Optional[str] = None
    process_id: Optional[int] = None
    headless: bool = True  # Default True

@router.get("/robot-status/{robot_name}")
def get_robot_status(robot_name: str):
    active_processes = ROBOT_STATUS.get(robot_name.lower(), set())
    return {
        "status": "running" if active_processes else "idle",
        "active_count": len(active_processes),
        "active_pids": list(active_processes)
    }

@router.get("/download-results")
def download_results(robot: str = "siget"):
    robot_name = robot.lower()
    if robot_name not in ROBOTS_CONFIG:
        raise HTTPException(status_code=400, detail="Robô inválido")
        
    config = ROBOTS_CONFIG[robot_name]
    download_dir = config["download_dir"]
    
    if not os.path.exists(download_dir):
        raise HTTPException(status_code=404, detail=f"Pasta de downloads não encontrada: {download_dir}")
    
    zip_filename = f"resultados_{robot_name}.zip"
    results_dir = os.path.join(ROOT_DIR, "Results")
    os.makedirs(results_dir, exist_ok=True)
    
    zip_path = os.path.join(results_dir, zip_filename)
    if os.path.exists(zip_path):
        os.remove(zip_path)
        
    shutil.make_archive(zip_path.replace('.zip', ''), 'zip', download_dir)
    return FileResponse(
        zip_path, 
        media_type='application/zip', 
        filename=zip_filename,
        headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
    )

def run_robot_logic(robot_name: str, process_id: int, competencia: Optional[str] = None, headless: bool = True, manual_args: Optional[dict] = None):
    """
    Core logic to execute a robot. Can be called from API or Scheduler.
    """
    robot_name = robot_name.lower()
    if robot_name not in ROBOTS_CONFIG:
        print(f"❌ Robô {robot_name} não encontrado nas configurações")
        return

    config = ROBOTS_CONFIG[robot_name]
    
    # Lógica de Limpeza: Se é o primeiro processo desse robô a rodar, limpa a pasta geral
    with STATUS_LOCK:
        if robot_name not in ROBOT_STATUS:
            ROBOT_STATUS[robot_name] = set()
        
        if not ROBOT_STATUS[robot_name]:
            print(f"Limpando pasta de downloads para início de nova sessão do {robot_name}...")
            if os.path.exists(config['download_dir']):
                shutil.rmtree(config['download_dir'], ignore_errors=True)
            os.makedirs(config['download_dir'], exist_ok=True)

        ROBOT_STATUS[robot_name].add(process_id)

    db = next(get_db())
    try:
        print(f"Iniciando {config['name']} (PID: {process_id})...")
        
        db_config = None
        target_agents = []
        
        if process_id:
            db_config = db.query(models.RobotConfig).filter(models.RobotConfig.id == process_id).first()
            if db_config:
                try:
                    agents_dict = json.loads(db_config.agents_json or '{}')
                    target_agents = list(agents_dict.keys())
                except: pass

        # --- IDEMPOTÊNCIA BLINDADA 🛡️ ---
        # Só podemos verificar se tivermos uma competência alvo explícita
        if competencia and target_agents:
            normalized_comp = competencia
            if "/" in competencia:
                try:
                    mes, ano = competencia.split("/")
                    normalized_comp = f"{ano}-{mes}"
                except: pass
            
            print(f"🛡️ Verificando idempotência para {len(target_agents)} agentes na competência {normalized_comp}...")
            
            # Busca documentos existentes para essa competência e códigos ONS
            existing_docs = db.query(models.DocumentRegistry.ons_code).filter(
                models.DocumentRegistry.competence_extracted == normalized_comp,
                models.DocumentRegistry.ons_code.in_(target_agents),
                models.DocumentRegistry.is_valid == True
            ).all()
            
            existing_agents = {doc.ons_code for doc in existing_docs}
            
            if existing_agents:
                print(f"✅ Documentos já validados encontrados para: {', '.join(existing_agents)}")
                # Filtra a lista de execução
                target_agents = [a for a in target_agents if a not in existing_agents]
                
                if not target_agents:
                    print(f"🎉 Todos os {len(existing_agents)} agentes já possuem documentos validados para {normalized_comp}.")
                    print(f"⏩ Pulando execução do robô para economizar recursos.")
                    return # Encerra sem rodar nada

                print(f"🚀 Executando APENAS para os {len(target_agents)} pendentes: {', '.join(target_agents)}")
            else:
                print("ℹ️ Nenhum documento validado encontrado anteriormente. Executando para todos.")
                
        # -----------------------------------

        # Comando simplificado
        cmd = ["python", config['script']]
        
        if db_config:
            if db_config.base: cmd.extend(["--empresa", db_config.base])
            if db_config.username: cmd.extend(["--user", db_config.username])
            if db_config.password: cmd.extend(["--password", db_config.password])
            
            # Passa a lista filtrada (ou original ser não houve filtro)
            if target_agents:
                cmd.extend(["--agente", ",".join(target_agents)])
        elif manual_args:
             # Fallback para argumentos manuais se não tiver config de banco
             if manual_args.get("empresa"): cmd.extend(["--empresa", manual_args["empresa"]])
             if manual_args.get("user"): cmd.extend(["--user", manual_args["user"]])
             if manual_args.get("password"): cmd.extend(["--password", manual_args["password"]])
             if manual_args.get("agente"): cmd.extend(["--agente", manual_args["agente"]])

        if competencia:
            cmd.extend(["--competencia", competencia])

        if headless:
            cmd.extend(["--headless"])

        cmd.extend(["--output_dir", config['download_dir']])

        print(f"Executando (PID {process_id}): {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        for line in process.stdout:
            print(f"[{config['name']}] {line.strip()}")
        
        process.wait()

    except Exception as e:
        print(f"Erro no robô {robot_name}: {e}")
    finally:
        with STATUS_LOCK:
            if robot_name in ROBOT_STATUS:
                ROBOT_STATUS[robot_name].discard(process_id)
        db.close()

def run_robot_and_organize(robot_name: str, process_id: int, competencia: Optional[str] = None, headless: bool = True, manual_args: Optional[dict] = None):
    """
    Wrapper para execuções MANUAIS: Roda o robô e depois organiza os arquivos.
    """
    # 1. Executa o script do robô (Lógica Bruta)
    run_robot_logic(robot_name, process_id, competencia, headless=headless, manual_args=manual_args)
    
    # 2. Chama o Validador para organizar os novos arquivos
    try:
        from ..scheduler import process_downloaded_files
        print(f"🧐 [VALIDADOR-MANUAL] Iniciando organização para {robot_name}...")
        process_downloaded_files(execution_id=None, robot_type=robot_name, robot_config_id=process_id)
    except Exception as e:
        print(f"⚠️ Erro no validador manual: {e}")

@router.post("/run-robot")
def run_robot(request: RobotRequest, background_tasks: BackgroundTasks):
    robot_name = request.robot_name.lower()
    
    if robot_name not in ROBOTS_CONFIG:
        raise HTTPException(status_code=400, detail="Robô inválido")
    
    process_id = request.process_id or 0
    competencia = request.competencia
    headless = request.headless
    
    # Extrai argumentos manuais do request
    manual_args = {
        "user": request.user,
        "password": request.password, 
        "agente": request.agente,
        "empresa": request.empresa
    }

    background_tasks.add_task(run_robot_and_organize, robot_name, process_id, competencia, headless, manual_args)
    return {"message": f"{robot_name} (PID {process_id}) iniciado", "status": "running"}

