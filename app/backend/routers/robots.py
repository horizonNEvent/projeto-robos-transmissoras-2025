from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
import os
import shutil
from sqlalchemy.orm import Session
from .. import database

from ..database import get_db

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
    }
}

# Estado global
ROBOT_STATUS = {}

class RobotRequest(BaseModel):
    robot_name: str
    base: str | None = None
    email: str | None = None

@router.get("/robot-status/{robot_name}")
def get_robot_status(robot_name: str):
    return {"status": ROBOT_STATUS.get(robot_name.lower(), "idle")}

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
    return FileResponse(zip_path, media_type='application/zip', filename=zip_filename)

@router.post("/run-robot")
def run_robot(request: RobotRequest, background_tasks: BackgroundTasks):
    robot_name = request.robot_name.lower()
    
    if robot_name not in ROBOTS_CONFIG:
        raise HTTPException(status_code=400, detail="Robô inválido. Opções: siget, cnt, pantanal, assu, tropicalia, firminopolis, evoltz, guaira")
    
    config = ROBOTS_CONFIG[robot_name]

    if robot_name == 'siget':
         siget_json_path = os.path.join(ROOT_DIR, "Data", "empresas.siget.json")
         if not os.path.exists(siget_json_path):
             raise HTTPException(status_code=400, detail="Configuração do Siget não encontrada. Configure no painel.")

    def exec_task():
        ROBOT_STATUS[robot_name] = "running"
        try:
            print(f"Iniciando {config['name']}...")
            if os.path.exists(config['download_dir']):
                shutil.rmtree(config['download_dir'])
            os.makedirs(config['download_dir'], exist_ok=True)
            
            process = subprocess.Popen(
                ["python", config['script']],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=ROOT_DIR,
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )
            
            for line in process.stdout:
                print(f"[{config['name']}] {line.strip()}")
            
            process.wait()
            ROBOT_STATUS[robot_name] = "finished" if process.returncode == 0 else "error"
        except Exception as e:
            print(f"Erro ao executar {config['name']}: {e}")
            ROBOT_STATUS[robot_name] = "error"

    background_tasks.add_task(exec_task)
    return {"message": f"{config['name']} iniciado", "status": "running"}
