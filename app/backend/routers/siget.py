from fastapi import APIRouter, HTTPException
import os
import json

router = APIRouter(prefix="/siget-config", tags=["siget"])

# Caminhos
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

@router.get("")
def get_siget_config():
    siget_json_path = os.path.join(ROOT_DIR, "Data", "empresas.siget.json")
    if not os.path.exists(siget_json_path):
        return {}
    with open(siget_json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

@router.post("")
def save_siget_config(config: dict):
    siget_json_path = os.path.join(ROOT_DIR, "Data", "empresas.siget.json")
    try:
        os.makedirs(os.path.dirname(siget_json_path), exist_ok=True)
        with open(siget_json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
