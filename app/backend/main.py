from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import subprocess
import os
import shutil
import zipfile
import json
from . import models, database

# Criação das tabelas
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependência DB
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Caminhos e Configurações dos Robôs
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EMPRESAS_JSON_PATH = os.path.join(ROOT_DIR, "Data", "empresas.json")

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
    }
}



@app.get("/download-results")
def download_results(robot: str = "siget"):
    robot_name = robot.lower()
    if robot_name not in ROBOTS_CONFIG:
        raise HTTPException(status_code=400, detail="Robô inválido")
        
    config = ROBOTS_CONFIG[robot_name]
    download_dir = config["download_dir"]
    
    if not os.path.exists(download_dir):
        raise HTTPException(status_code=404, detail=f"Pasta de downloads não encontrada: {download_dir}")
    
    # Salva o ZIP na pasta Results
    zip_filename = f"resultados_{robot_name}.zip"
    results_dir = os.path.join(ROOT_DIR, "Results")
    os.makedirs(results_dir, exist_ok=True)
    
    zip_path = os.path.join(results_dir, zip_filename)
    
    if os.path.exists(zip_path):
        os.remove(zip_path)
        
    shutil.make_archive(zip_path.replace('.zip', ''), 'zip', download_dir)
    
    return FileResponse(zip_path, media_type='application/zip', filename=zip_filename)

class RobotRequest(BaseModel):
    robot_name: str
    base: str | None = None
    email: str | None = None

class EmpresaBase(BaseModel):
    codigo_ons: str
    nome_empresa: str
    base: str
    ativo: bool = True

class EmpresaCreate(EmpresaBase):
    pass

class EmpresaUpdate(EmpresaBase):
    pass

def update_json_file(db: Session):
    """Reescreve o arquivo empresas.json com todas as empresas do banco de dados."""
    empresas = db.query(models.Empresa).all()
    data = {}
    
    for emp in empresas:
        if emp.base not in data:
            data[emp.base] = {}
        data[emp.base][emp.codigo_ons] = emp.nome_empresa
        
    with open(EMPRESAS_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

@app.get("/empresas")
def list_empresas(db: Session = Depends(get_db)):
    return db.query(models.Empresa).all()

@app.post("/empresas")
def create_empresa(empresa: EmpresaCreate, db: Session = Depends(get_db)):
    db_empresa = models.Empresa(
        codigo_ons=empresa.codigo_ons,
        nome_empresa=empresa.nome_empresa,
        base=empresa.base
    )
    db.add(db_empresa)
    db.commit()
    db.refresh(db_empresa)
    update_json_file(db)
    return db_empresa

@app.put("/empresas/{empresa_id}")
def update_empresa(empresa_id: int, empresa: EmpresaUpdate, db: Session = Depends(get_db)):
    db_empresa = db.query(models.Empresa).filter(models.Empresa.id == empresa_id).first()
    if not db_empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    
    db_empresa.codigo_ons = empresa.codigo_ons
    db_empresa.nome_empresa = empresa.nome_empresa
    db_empresa.base = empresa.base
    
    db.commit()
    db.refresh(db_empresa)
    update_json_file(db)
    return db_empresa

@app.delete("/empresas/{empresa_id}")
def delete_empresa(empresa_id: int, db: Session = Depends(get_db)):
    db_empresa = db.query(models.Empresa).filter(models.Empresa.id == empresa_id).first()
    if not db_empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    
    db.delete(db_empresa)
    db.commit()
    update_json_file(db)
    return {"message": "Deletado com sucesso"}

@app.post("/empresas/sync")
def sync_empresas(db: Session = Depends(get_db)):
    # Lê do empresas.json e popula o banco
    if os.path.exists(EMPRESAS_JSON_PATH):
        try:
            with open(EMPRESAS_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Estrutura esperada: {"AETE": {"4284": "Anemus_I", ...}}
                for base_name, emps in data.items():
                    for codigo, nome in emps.items():
                        existing = db.query(models.Empresa).filter(models.Empresa.codigo_ons == codigo).first()
                        if not existing:
                            try:
                                db.add(models.Empresa(codigo_ons=str(codigo), nome_empresa=nome, base=base_name))
                                db.commit()
                            except Exception as e:
                                print(f"Erro ao inserir {codigo}: {e}")
                                db.rollback()
            return {"status": "synced"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}
    return {"status": "file not found"}

# Estado global dos robôs (em memória)
ROBOT_STATUS = {}

@app.get("/robot-status/{robot_name}")
def get_robot_status(robot_name: str):
    return {"status": ROBOT_STATUS.get(robot_name.lower(), "idle")}

@app.get("/siget-config")
def get_siget_config():
    siget_json_path = os.path.join(ROOT_DIR, "Data", "empresas.siget.json")
    if not os.path.exists(siget_json_path):
        return {}
    with open(siget_json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

@app.post("/siget-config")
def save_siget_config(config: dict):
    siget_json_path = os.path.join(ROOT_DIR, "Data", "empresas.siget.json")
    try:
        with open(siget_json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-robot")
def run_robot(request: RobotRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    robot_name = request.robot_name.lower()
    
    if robot_name not in ROBOTS_CONFIG:
        raise HTTPException(status_code=400, detail="Robô inválido. Opções: siget, cnt, pantanal, assu, tropicalia, firminopolis, evoltz")
    
    # ... (lógica existing Siget config - mantida igual)
    config = ROBOTS_CONFIG[robot_name]
    
    # Siget agora usa a configuração persistente em Data/empresas.siget.json
    if robot_name == 'siget':
         siget_json_path = os.path.join(ROOT_DIR, "Data", "empresas.siget.json")
         if not os.path.exists(siget_json_path):
             raise HTTPException(status_code=400, detail="Configuração do Siget não encontrada. Configure no painel.")

    def exec_task():
        ROBOT_STATUS[robot_name] = "running"
        try:
            print(f"Iniciando {config['name']}...")
            
            # Limpa diretório de download
            if os.path.exists(config['download_dir']):
                shutil.rmtree(config['download_dir'])
            os.makedirs(config['download_dir'], exist_ok=True)
            
            # Execução com streaming de logs para o terminal
            process = subprocess.Popen(
                ["python", config['script']],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=ROOT_DIR,
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )
            
            # Lê a saída em tempo real
            for line in process.stdout:
                print(f"[{config['name']}] {line.strip()}")
            
            process.wait()
            
            if process.returncode == 0:
                print(f"{config['name']} finalizado com sucesso.")
                ROBOT_STATUS[robot_name] = "finished"
            else:
                print(f"{config['name']} finalizado com erro (code {process.returncode}).")
                ROBOT_STATUS[robot_name] = "error"
        except Exception as e:
            print(f"Erro ao executar {config['name']}: {e}")
            ROBOT_STATUS[robot_name] = "error"

    background_tasks.add_task(exec_task)
    return {"message": f"{config['name']} iniciado", "status": "running"}


