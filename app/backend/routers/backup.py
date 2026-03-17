import os
import shutil
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from typing import List

router = APIRouter(prefix="/backup", tags=["backup"])

BACKUP_DIR = "bkp_banco"
DB_FILE = "sql_app.db"

def ensure_backup_dir():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

@router.post("/create")
def create_backup():
    """Cria um backup do banco de dados sql_app.db na pasta bkp_banco."""
    try:
        ensure_backup_dir()
        
        if not os.path.exists(DB_FILE):
            raise HTTPException(status_code=404, detail="Banco de dados sql_app.db não encontrado.")
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        shutil.copy2(DB_FILE, backup_path)
        
        return {
            "message": "Backup gerado com sucesso",
            "filename": backup_filename,
            "path": backup_path,
            "timestamp": timestamp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
def list_backups():
    """Lista todos os backups disponíveis na pasta bkp_banco."""
    try:
        if not os.path.exists(BACKUP_DIR):
            return []
            
        backups = []
        for f in os.listdir(BACKUP_DIR):
            if f.endswith(".db"):
                path = os.path.join(BACKUP_DIR, f)
                stats = os.stat(path)
                backups.append({
                    "filename": f,
                    "size": stats.st_size,
                    "created_at": datetime.fromtimestamp(stats.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                })
        
        # Ordenar pelo mais recente
        backups.sort(key=lambda x: x['filename'], reverse=True)
        return backups
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{filename}")
def download_backup(filename: str):
    """Permite baixar um arquivo de backup específico."""
    path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Arquivo de backup não encontrado.")
    
    return FileResponse(path, filename=filename, media_type='application/x-sqlite3')

@router.delete("/{filename}")
def delete_backup(filename: str):
    """Remove um arquivo de backup."""
    path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Arquivo de backup não encontrado.")
    
    os.remove(path)
    return {"message": f"Backup {filename} removido com sucesso."}
