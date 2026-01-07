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
        "download_dir": get_download_path("sigetplus"),
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

def run_robot_logic(robot_name: str, process_id: int, competencia: Optional[str] = None):
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
        if process_id:
            db_config = db.query(models.RobotConfig).filter(models.RobotConfig.id == process_id).first()
        
        cmd = ["python", config['script']]
        
        final_empresa = None
        final_agente = None
        final_user = None
        final_pass = None
        final_competencia = competencia
        
        if db_config:
            final_empresa = db_config.base
            final_user = db_config.username
            final_pass = db_config.password
            try:
                agents_dict = json.loads(db_config.agents_json or '{}')
                if agents_dict:
                    final_agente = ",".join(agents_dict.keys())
            except: pass

        if final_empresa: cmd.extend(["--empresa", final_empresa])
        if final_agente: cmd.extend(["--agente", final_agente])
        if final_user: cmd.extend(["--user", final_user])
        if final_pass: cmd.extend(["--password", final_pass])
        if final_competencia: cmd.extend(["--competencia", final_competencia])
        cmd.extend(["--output_dir", config['download_dir']])

        print(f"Executando comando (PID {process_id}): {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=ROOT_DIR,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        for line in process.stdout:
            print(f"[{config['name']}-{process_id}] {line.strip()}")
        
        process.wait()

        # 🔥 AÇÃO DEFINITIVA: Organiza e registra os documentos após o robô terminar
        # Fazemos o import local para evitar erro de importação circular
        try:
            from ..scheduler import process_downloaded_files
            print(f"🧐 [VALIDADOR] Escaneando arquivos baixados por {robot_name}...")
            process_downloaded_files(execution_id=None, robot_type=robot_name)
        except Exception as e:
            print(f"⚠️ Erro ao organizar arquivos pós-execução: {e}")

    except Exception as e:
        print(f"Erro ao executar {config['name']} (PID {process_id}): {e}")
        raise e
    finally:
        with STATUS_LOCK:
            if robot_name in ROBOT_STATUS:
                ROBOT_STATUS[robot_name].discard(process_id)
        db.close()

@router.post("/run-robot")
def run_robot(request: RobotRequest, background_tasks: BackgroundTasks):
    robot_name = request.robot_name.lower()
    
    if robot_name not in ROBOTS_CONFIG:
        raise HTTPException(status_code=400, detail="Robô inválido")
    
    process_id = request.process_id or 0
    competencia = request.competencia

    background_tasks.add_task(run_robot_logic, robot_name, process_id, competencia)
    return {"message": f"{robot_name} (PID {process_id}) iniciado", "status": "running"}
