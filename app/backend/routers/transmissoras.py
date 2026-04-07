from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
import os
import io
import json
import pandas as pd
from datetime import datetime
import unicodedata
from .. import models
from ..database import get_db

router = APIRouter(prefix="/transmissoras", tags=["transmissoras"])

@router.delete("")
def clear_transmissoras(db: Session = Depends(get_db)):
    db.query(models.Transmissora).delete()
    db.commit()
    return {"message": "Todas as transmissoras foram removidas."}

@router.get("")
def list_transmissoras(db: Session = Depends(get_db)):
    return db.query(models.Transmissora).all()

@router.post("/upload")
async def upload_transmissoras(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content))
        
        # 1. Normalização de Colunas
        def normalize_name(name):
            if not name: return ""
            n = unicodedata.normalize('NFD', str(name))
            n = "".join([c for c in n if unicodedata.category(c) != 'Mn'])
            n = n.strip().lower()
            n = n.replace(" ", "_").replace(".", "").replace("-", "").replace("/", "")
            return n

        df.columns = [normalize_name(c) for c in df.columns]
        
        # 2. Identificação de Identificador (CNPJ ou ID)
        key_col = None
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
                if row.isnull().all(): continue
                
                chave = str(row[key_col]).strip()
                if not chave or chave == 'nan': continue

                if 'cnpj' in key_col.lower() and chave.isdigit():
                    chave = chave.zfill(14)

                db_trans = db.query(models.Transmissora).filter(models.Transmissora.cnpj == chave).first()
                
                row_dict = {k: (str(v).strip() if v is not None and not pd.isna(v) else None) for k, v in row.to_dict().items()}

                rep_data = {
                    "nome": str(row_dict.get('nome_do_representante', '')).strip(),
                    "email": str(row_dict.get('email', '')).strip(),
                    "telefone": str(row_dict.get('telefone', '')).strip(),
                    "funcao": str(row_dict.get('funcao_do_representante', '')).strip()
                }

                if db_trans:
                    existing_data = json.loads(db_trans.dados_json or "{}")
                    
                    for k, v in row_dict.items():
                        if v is not None and str(v).strip() != "" and str(v).lower() != "nan":
                            existing_data[k] = v
                    
                    if 'representantes_list' not in existing_data or not isinstance(existing_data['representantes_list'], list):
                        existing_data['representantes_list'] = []
                        old_rep = {
                            "nome": str(existing_data.get('nome_do_representante', '')),
                            "email": str(existing_data.get('email', '')),
                            "telefone": str(existing_data.get('telefone', '')),
                            "funcao": str(existing_data.get('funcao_do_representante', ''))
                        }
                        if old_rep['nome'] or old_rep['email']:
                            existing_data['representantes_list'].append(old_rep)

                    is_duplicate = any(r.get('email') == rep_data['email'] and r.get('nome') == rep_data['nome'] for r in existing_data['representantes_list'])
                    if not is_duplicate and (rep_data['nome'] or rep_data['email']):
                        existing_data['representantes_list'].append(rep_data)

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

from pydantic import BaseModel
import subprocess
from .robots import ROBOT_PYTHON

class AmseCredentials(BaseModel):
    user: str
    password: str

@router.post("/update-amse")
def update_transmissoras_amse(creds: AmseCredentials, db: Session = Depends(get_db)):
    """
    Executa o robô AMSE para atualizar a tabela de transmissoras.
    """
    try:
        # Caminho do script
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        script_path = os.path.join(root_dir, "Robots", "amse.py")
        
        if not os.path.exists(script_path):
            raise HTTPException(status_code=500, detail="Script do robô AMSE não encontrado.")

        cmd = [ROBOT_PYTHON, script_path, "--user", creds.user, "--password", creds.password, "--update-db"]
        
        # Executa
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        stdout, _ = process.communicate()
        
        if process.returncode != 0:
            print(f"Erro AMSE: {stdout}")
            raise HTTPException(status_code=500, detail=f"Erro na execução do robô: {stdout}")
            
        return {"message": "Atualização concluída com sucesso.", "logs": stdout}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
