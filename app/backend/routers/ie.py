from fastapi import APIRouter, HTTPException
import os
import json

router = APIRouter(prefix="/ie-config", tags=["ie"])

# Caminhos
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

@router.get("")
def get_ie_config():
    ie_json_path = os.path.join(ROOT_DIR, "Data", "empresas.ie.json")
    if not os.path.exists(ie_json_path):
        return {}
    with open(ie_json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

@router.post("")
def save_ie_config(config: dict):
    ie_json_path = os.path.join(ROOT_DIR, "Data", "empresas.ie.json")
    try:
        os.makedirs(os.path.dirname(ie_json_path), exist_ok=True)
        with open(ie_json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
