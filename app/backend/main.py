# Backend started
from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import subprocess
import os
import shutil
import zipfile
import json
import io
import pandas as pd
from datetime import datetime
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

@app.delete("/transmissoras")
def clear_transmissoras(db: Session = Depends(get_db)):
    db.query(models.Transmissora).delete()
    db.commit()
    return {"message": "Todas as transmissoras foram removidas."}

@app.get("/transmissoras")
def list_transmissoras(db: Session = Depends(get_db)):
    return db.query(models.Transmissora).all()

@app.post("/transmissoras/upload")
async def upload_transmissoras(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        # Lê a planilha (Pandas suporta xls e xlsx)
        df = pd.read_excel(io.BytesIO(content))
        
        # 1. Normalização de Colunas
        import unicodedata
        def normalize_name(name):
            if not name: return ""
            # Remove acentos
            n = unicodedata.normalize('NFD', str(name))
            n = "".join([c for c in n if unicodedata.category(c) != 'Mn'])
            n = n.strip().lower()
            n = n.replace(" ", "_").replace(".", "").replace("-", "").replace("/", "")
            return n

        df.columns = [normalize_name(c) for c in df.columns]
        
        # 2. Identificação de Identificador (CNPJ ou ID)
        key_col = None
        # Prioridade para CNPJ
        for col in df.columns:
            if 'cnpj' in col:
                key_col = col
                break
        
        if not key_col:
            for col in df.columns:
                if col in ['codigo', 'id', 'ons', 'codigo_ons']:
                    key_col = col
                    break
        
        if not key_col:
            raise HTTPException(status_code=400, detail="Planilha deve conter uma coluna 'cnpj' ou identificador único.")

        stats = {"inserted": 0, "updated": 0, "errors": 0}
        
        for _, row in df.iterrows():
            try:
                # Pula linhas totalmente vazias
                if row.isnull().all(): continue
                
                chave = str(row[key_col]).strip()
                if not chave or chave == 'nan': continue

                # Normalização de CNPJ (Padding)
                if 'cnpj' in key_col.lower() and chave.isdigit():
                    chave = chave.zfill(14)

                # Busca no banco
                db_trans = db.query(models.Transmissora).filter(models.Transmissora.cnpj == chave).first()
                
                # Prepara dados dinâmicos (JSON)
                # Prepara dados dinâmicos (JSON)
                row_dict = {k: (str(v).strip() if v is not None and not pd.isna(v) else None) for k, v in row.to_dict().items()}

                # Prepara dados do representante atual da linha
                rep_data = {
                    "nome": str(row_dict.get('nome_do_representante', '')).strip(),
                    "email": str(row_dict.get('email', '')).strip(),
                    "telefone": str(row_dict.get('telefone', '')).strip(),
                    "funcao": str(row_dict.get('funcao_do_representante', '')).strip()
                }

                if db_trans:
                    # UPDATE segura (planilha ganha se não estiver vazia)
                    existing_data = json.loads(db_trans.dados_json or "{}")
                    
                    # Merge do JSON (campos normais)
                    for k, v in row_dict.items():
                        if v is not None and str(v).strip() != "" and str(v).lower() != "nan":
                            existing_data[k] = v
                    
                    # Gestão da lista de representantes
                    if 'representantes_list' not in existing_data or not isinstance(existing_data['representantes_list'], list):
                        # Cria lista inicial com o representante que já estava lá (se houver)
                        existing_data['representantes_list'] = []
                        old_rep = {
                            "nome": str(existing_data.get('nome_do_representante', '')),
                            "email": str(existing_data.get('email', '')),
                            "telefone": str(existing_data.get('telefone', '')),
                            "funcao": str(existing_data.get('funcao_do_representante', ''))
                        }
                        if old_rep['nome'] or old_rep['email']:
                            existing_data['representantes_list'].append(old_rep)

                    # Adiciona novo se não duplicado
                    is_duplicate = any(r.get('email') == rep_data['email'] and r.get('nome') == rep_data['nome'] for r in existing_data['representantes_list'])
                    if not is_duplicate and (rep_data['nome'] or rep_data['email']):
                        existing_data['representantes_list'].append(rep_data)

                    # Atualiza campos fixos mapeados
                    if 'nome' in row_dict and row_dict['nome']: db_trans.nome = str(row_dict['nome'])
                    elif 'nome_do_agente' in row_dict and row_dict['nome_do_agente']: db_trans.nome = str(row_dict['nome_do_agente'])
                    elif 'razao_social' in row_dict and row_dict['razao_social']: db_trans.nome = str(row_dict['razao_social'])
                    
                    if 'sigla' in row_dict and row_dict['sigla']: db_trans.sigla = str(row_dict['sigla'])
                    elif 'sigla_do_agente' in row_dict and row_dict['sigla_do_agente']: db_trans.sigla = str(row_dict['sigla_do_agente'])
                    
                    if 'grupo' in row_dict and row_dict['grupo']: db_trans.grupo = str(row_dict['grupo'])
                    elif 'grupo_economico' in row_dict and row_dict['grupo_economico']: db_trans.grupo = str(row_dict['grupo_economico'])
                    
                    if 'codigo_ons' in row_dict and row_dict['codigo_ons']: db_trans.codigo_ons = str(row_dict['codigo_ons'])
                    elif 'codigo' in row_dict and row_dict['codigo']: db_trans.codigo_ons = str(row_dict['codigo'])
                    elif 'ons' in row_dict and row_dict['ons']: db_trans.codigo_ons = str(row_dict['ons'])
                    
                    db_trans.dados_json = json.dumps(existing_data, ensure_ascii=False)
                    db_trans.ultima_atualizacao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    stats["updated"] += 1
                else:
                    # INSERT
                    row_dict['representantes_list'] = [rep_data] if rep_data['nome'] or rep_data['email'] else []
                    new_trans = models.Transmissora(
                        cnpj=chave,
                        nome=str(row_dict.get('nome', row_dict.get('nome_do_agente', row_dict.get('razao_social', '')))),
                        sigla=str(row_dict.get('sigla', row_dict.get('sigla_do_agente', ''))),
                        grupo=str(row_dict.get('grupo', row_dict.get('grupo_economico', ''))),
                        codigo_ons=str(row_dict.get('codigo_ons', row_dict.get('codigo', row_dict.get('ons', '')))),
                        dados_json=json.dumps(row_dict, ensure_ascii=False),
                        ultima_atualizacao=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                    db.add(new_trans)
                    stats["inserted"] += 1
                
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Erro na linha: {e}")
                stats["errors"] += 1

        return {"message": "Processamento concluído", "stats": stats}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler planilha: {str(e)}")

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


