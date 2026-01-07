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
ROBOTS_CONFIG = {
    "siget": {
        "script": os.path.join(ROOT_DIR, "Robots", "siget.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\SIGETPLUS",
        "name": "WebSiget"
    },
    "cnt": {
        "script": os.path.join(ROOT_DIR, "Robots", "cnt.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\CNT",
        "name": "WebCnt"
    },
    "pantanal": {
        "script": os.path.join(ROOT_DIR, "Robots", "pantanal.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\PANTANAL",
        "name": "WebPantanal"
    },
    "assu": {
        "script": os.path.join(ROOT_DIR, "Robots", "assu.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\ASSU",
        "name": "WebAssu"
    },
    "tropicalia": {
        "script": os.path.join(ROOT_DIR, "Robots", "tropicalia.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\TROPICALIA",
        "name": "WebTropicalia"
    },
    "firminopolis": {
        "script": os.path.join(ROOT_DIR, "Robots", "firminopolis.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\FIRMINOPOLIS",
        "name": "WebFirminopolis"
    },
    "evoltz": {
        "script": os.path.join(ROOT_DIR, "Robots", "evoltz.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\EVOLTZ",
        "name": "WebEvoltz"
    },
    "guaira": {
        "script": os.path.join(ROOT_DIR, "Robots", "guaira.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\GUAIRA",
        "name": "WebGuaira"
    },
    "itamaraca": {
        "script": os.path.join(ROOT_DIR, "Robots", "itamaraca.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\ITAMARACA",
        "name": "WebItamaraca"
    },
    "colinas": {
        "script": os.path.join(ROOT_DIR, "Robots", "colinas.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\COLINAS",
        "name": "WebColinas"
    },
    "simoes": {
        "script": os.path.join(ROOT_DIR, "Robots", "simoes.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\SIMOES",
        "name": "WebSimoes"
    },
    "fs": {
        "script": os.path.join(ROOT_DIR, "Robots", "fs.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\FS",
        "name": "WebFS"
    },
    "vineyards": {
        "script": os.path.join(ROOT_DIR, "Robots", "vineyards.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\VINEYARDS",
        "name": "WebVineyards"
    },
    "agua_vermelha": {
        "script": os.path.join(ROOT_DIR, "Robots", "agua_vermelha.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\AGUAVERMELHA",
        "name": "WebAguaVermelha"
    },
    "webieriachogrande": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIERIACHOGRANDE.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIERIACHOGRANDE",
        "name": "WebIERIACHOGRANDE"
    },
    "webiecteep": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIECTEEP.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIECTEEP",
        "name": "WebIECTEEP"
    },
    "webieaguapei": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEAGUAPEI.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEAGUAPEI",
        "name": "WebIEAGUAPEI"
    },
    "webiebiguacu": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEBIGUACU.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEBIGUACU",
        "name": "WebIEBIGUACU"
    },
    "webiegaranhuns": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEGARANHUNS.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEGARANHUNS",
        "name": "WebIEGARANHUNS"
    },
    "webieitapura": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEITAPURA.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEITAPURA",
        "name": "WebIEITAPURA"
    },
    "webieitaquere": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEITAQUERE.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEITAQUERE",
        "name": "WebIEITAQUERE"
    },
    "webieitaunas": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEITAUNAS.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEITAUNAS",
        "name": "WebIEITAUNAS"
    },
    "webieivai": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEIVAI.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEIVAI",
        "name": "WebIEIVAI"
    },
    "webiejaguar6": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEJAGUAR6.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEJAGUAR6",
        "name": "WebIEJAGUAR6"
    },
    "webiejaguar8": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEJAGUAR8.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEJAGUAR8",
        "name": "WebIEJAGUAR8"
    },
    "webiejaguar9": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEJAGUAR9.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEJAGUAR9",
        "name": "WebIEJAGUAR9"
    },
    "webiemadeira": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEMADEIRA.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEMADEIRA",
        "name": "WebIEMADEIRA"
    },
    "webiemg": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEMG.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEMG",
        "name": "WebIEMG"
    },
    "webienne": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIENNE.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIENNE",
        "name": "WebIENNE"
    },
    "webiepinheiros": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIEPINHEIROS.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIEPINHEIROS",
        "name": "WebIEPINHEIROS"
    },
    "webieserradojapi": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIESERRADOJAPI.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIESERRADOJAPI",
        "name": "WebIESERRADOJAPI"
    },
    "webiesul": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIESUL.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIESUL",
        "name": "WebIESUL"
    },
    "webietibagi": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebIETIBAGI.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebIETIBAGI",
        "name": "WebIETIBAGI"
    },
    "webengie": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebEngie.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebEngie",
        "name": "WebEngie"
    },
    "webettm": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebETTM.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebETTM",
        "name": "WebETTM"
    },
    "websigetpublic": {
        "script": os.path.join(ROOT_DIR, "Robots", "WebSigetPublic.py"),
        "download_dir": r"C:\Users\Bruno\Downloads\TUST\WebSigetPublic",
        "name": "WebSigetPublic"
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

@router.post("/run-robot")
def run_robot(request: RobotRequest, background_tasks: BackgroundTasks):
    robot_name = request.robot_name.lower()
    
    if robot_name not in ROBOTS_CONFIG:
        raise HTTPException(status_code=400, detail="Robô inválido")
    
    config = ROBOTS_CONFIG[robot_name]
    process_id = request.process_id or 0

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

    async def exec_task():
        db = next(get_db())
        try:
            print(f"Iniciando {config['name']} (PID: {process_id})...")
            
            db_config = None
            if process_id:
                db_config = db.query(models.RobotConfig).filter(models.RobotConfig.id == process_id).first()
            
            cmd = ["python", config['script']]
            
            final_empresa = request.empresa
            final_agente = request.agente
            final_user = request.user
            final_pass = request.password
            final_competencia = request.competencia
            
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
        except Exception as e:
            print(f"Erro ao executar {config['name']} (PID {process_id}): {e}")
        finally:
            with STATUS_LOCK:
                if robot_name in ROBOT_STATUS:
                    ROBOT_STATUS[robot_name].discard(process_id)
            db.close()

    background_tasks.add_task(exec_task)
    return {"message": f"{config['name']} (PID {process_id}) iniciado", "status": "running"}
