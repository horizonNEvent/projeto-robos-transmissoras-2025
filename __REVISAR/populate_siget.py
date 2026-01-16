import sqlite3
import json

# Configurações fornecidas pelo usuário, ajustadas com os códigos ONS corretos
configs_to_add = [
    {
        "base": "SJP",
        "email": "faturas.sjp@americaenergia.com.br",
        "description": "Empresa com agentes SJP1 a SJP6",
        "agents": {
            "3859": "SJP1",
            "3860": "SJP2",
            "3861": "SJP3",
            "3862": "SJP4",
            "3863": "SJP5",
            "3864": "SJP6"
        }
    },
    {
        "base": "LIBRA",
        "email": "faturas.libra@americaenergia.com.br",
        "description": "Empresa com agente LIBRA",
        "agents": {
            "8011": "LIBRA"
        }
    },
    {
        "base": "COREMAS",
        "email": "fatura.coremas@americaenergia.com.br",
        "description": "Empresa com agentes COR1, COR2 e COR3",
        "agents": {
            "3740": "COR1",
            "3741": "COR2",
            "3750": "COR3"
        }
    },
    {
        "base": "RE",
        "email": "tust@pontalenergy.com",
        "description": "Empresa principal com múltiplos agentes CEC e ITA",
        "agents": {
            "3430": "CECA",
            "3431": "CECB",
            "3432": "CECC",
            "4415": "CECD",
            "4315": "CECE",
            "4316": "CECF",
            "3502": "ITA1",
            "3497": "ITA2",
            "3503": "ITA3",
            "3530": "ITA4",
            "3498": "ITA5",
            "3531": "ITA6",
            "3532": "ITA7",
            "3537": "ITA8",
            "3538": "ITA9",
            "4313": "BRJA",
            "4314": "BRJB"
        }
    },
    {
        "base": "DE",
        "email": "services.easytust@diamanteenergia.com.br",
        "description": "Empresa com agente DE único",
        "agents": {
            "3748": "DE"
        }
    },
    {
        "base": "AETE",
        "email": "tust@2wecobank.com.br",
        "description": "Empresa AETE",
        "agents": {
            "4284": "Anemus_I",
            "4292": "Anemus_II",
            "4319": "Anemus_III"
        }
    }
]

conn = sqlite3.connect('d:/Workspace/Tust-AETE/sql_app.db')
cursor = conn.cursor()

print("Inserindo parametrizações para o robô 'siget'...")

added_count = 0
for config in configs_to_add:
    cursor.execute("""
        INSERT INTO robot_configs (robot_type, base, label, username, password, agents_json, active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        'siget', 
        config['base'], 
        config['description'], 
        config['email'], 
        "SENHA_A_DEFINIR", 
        json.dumps(config['agents']), 
        1
    ))
    added_count += 1

conn.commit()
conn.close()

print(f"Sucesso! {added_count} parametrizações para 'siget' foram inseridas.")
