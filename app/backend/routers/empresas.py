from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import os
import json
from pydantic import BaseModel
from .. import models
from ..database import get_db

router = APIRouter(prefix="/empresas", tags=["empresas"])

# Caminhos
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EMPRESAS_JSON_PATH = os.path.join(ROOT_DIR, "Data", "empresas.json")
EMPRESAS_EQUATORIAL_JSON_PATH = os.path.join(ROOT_DIR, "Data", "empresas.equatorial.json")

class EmpresaBase(BaseModel):
    codigo_ons: str
    nome_empresa: str
    cnpj: str | None = None
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
        data[emp.base][emp.codigo_ons] = {
            "nome": emp.nome_empresa,
            "cnpj": emp.cnpj
        }
        
    os.makedirs(os.path.dirname(EMPRESAS_JSON_PATH), exist_ok=True)
    with open(EMPRESAS_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

@router.get("")
def list_empresas(db: Session = Depends(get_db)):
    return db.query(models.Empresa).all()

@router.post("")
def create_empresa(empresa: EmpresaCreate, db: Session = Depends(get_db)):
    db_empresa = models.Empresa(
        codigo_ons=empresa.codigo_ons,
        nome_empresa=empresa.nome_empresa,
        cnpj=empresa.cnpj,
        base=empresa.base
    )
    db.add(db_empresa)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao criar empresa: {str(e)}")
    db.refresh(db_empresa)
    update_json_file(db)
    return db_empresa

@router.put("/{empresa_id}")
def update_empresa(empresa_id: int, empresa: EmpresaUpdate, db: Session = Depends(get_db)):
    db_empresa = db.query(models.Empresa).filter(models.Empresa.id == empresa_id).first()
    if not db_empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    
    db_empresa.codigo_ons = empresa.codigo_ons
    db_empresa.nome_empresa = empresa.nome_empresa
    db_empresa.cnpj = empresa.cnpj
    db_empresa.base = empresa.base
    
    db.commit()
    db.refresh(db_empresa)
    update_json_file(db)
    return db_empresa

@router.delete("/{empresa_id}")
def delete_empresa(empresa_id: int, db: Session = Depends(get_db)):
    db_empresa = db.query(models.Empresa).filter(models.Empresa.id == empresa_id).first()
    if not db_empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    
    db.delete(db_empresa)
    db.commit()
    update_json_file(db)
    return {"message": "Deletado com sucesso"}

@router.post("/sync")
def sync_empresas(db: Session = Depends(get_db)):
    # Prioridade para o arquivo equatorial que tem os CNPJs
    json_to_load = EMPRESAS_EQUATORIAL_JSON_PATH if os.path.exists(EMPRESAS_EQUATORIAL_JSON_PATH) else EMPRESAS_JSON_PATH
    
    if os.path.exists(json_to_load):
        try:
            with open(json_to_load, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for base_name, emps in data.items():
                    for codigo, info in emps.items():
                        # Suporta tanto o formato antigo (str) quanto novo (dict)
                        nome = info["nome"] if isinstance(info, dict) else info
                        cnpj = info.get("cnpj") if isinstance(info, dict) else None
                        
                        existing = db.query(models.Empresa).filter(models.Empresa.codigo_ons == str(codigo)).first()
                        if not existing:
                            try:
                                db.add(models.Empresa(codigo_ons=str(codigo), nome_empresa=nome, cnpj=cnpj, base=base_name))
                                db.commit()
                            except Exception as e:
                                print(f"Erro ao inserir {codigo}: {e}")
                                db.rollback()
                        else:
                            # Se ja existe, atualiza o CNPJ se estiver vazio
                            if not existing.cnpj and cnpj:
                                existing.cnpj = cnpj
                                existing.nome_empresa = nome
                                db.commit()
                                
            return {"status": "synced", "source": os.path.basename(json_to_load)}
        except Exception as e:
            return {"status": "error", "detail": str(e)}
    return {"status": "file not found"}

@router.get("/mapping")
def get_mapping():
    if os.path.exists(EMPRESAS_JSON_PATH):
        try:
            with open(EMPRESAS_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {}
