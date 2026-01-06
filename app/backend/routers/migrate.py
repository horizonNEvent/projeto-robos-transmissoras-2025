from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import models, database
import os
import json

router = APIRouter(prefix="/config/migrate", tags=["config"])

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

@router.post("")
def migrate_json_to_db(db: Session = Depends(database.get_db)):
    # Limpa config atual
    db.query(models.RobotConfig).delete()
    
    # Siget
    siget_path = os.path.join(ROOT_DIR, "Data", "empresas.siget.json")
    if os.path.exists(siget_path):
        with open(siget_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for base, info in data.items():
                agents = info.get('agentes', {})
                # Se agentes for array de dicts (formato antigo?), normaliza
                if isinstance(agents, list):
                    normalized = {}
                    for item in agents:
                         k = list(item.keys())[0]
                         normalized[k] = item[k]
                    agents = normalized
                
                config = models.RobotConfig(
                    robot_type='SIGET',
                    base=base,
                    label=base,
                    username=info.get('email', ''),
                    password='', # Senha não era salva no JSON do Siget nesse formato
                    agents_json=json.dumps(agents),
                    active=True
                )
                db.add(config)

    # IE
    ie_path = os.path.join(ROOT_DIR, "Data", "empresas.ie.json")
    if os.path.exists(ie_path):
        with open(ie_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for label, info in data.items():
                # Tenta inferir a base (RE, AE, DE, AETE)
                base = "AETE"
                if label.upper() in ["RE", "AE", "DE", "AETE"]:
                    base = label.upper()
                
                config = models.RobotConfig(
                    robot_type='WEBIE',
                    base=base,
                    label=label,
                    username=info.get('usuario', ''),
                    password=info.get('senha', ''),
                    agents_json=json.dumps(info.get('agentes', {})),
                    active=True
                )
                db.add(config)
    
    db.commit()
    return {"status": "migration complete"}
