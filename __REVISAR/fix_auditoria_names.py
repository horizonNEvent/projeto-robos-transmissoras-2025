import os
import json
from sqlalchemy.orm import Session
from app.backend.database import SessionLocal, engine
from app.backend import models

def fix_names():
    # 1. Carrega empresas.json
    try:
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Data', 'empresas.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            EMPRESAS_DATA = json.load(f)
            print(f"✅ empresas.json carregado com {len(EMPRESAS_DATA)} bases.")
    except Exception as e:
        print(f"❌ Erro ao carregar empresas.json: {e}")
        return

    db = SessionLocal()
    try:
        # Busca TODOS os documentos para garantir consistência
        docs = db.query(models.DocumentRegistry).all()
        
        print(f"🔍 Verificando {len(docs)} documentos no total...")
        
        updated_count = 0
        for doc in docs:
            ons = doc.ons_code
            base = doc.base
            
            new_name = None
            
            # Busca no JSON
            if base and ons:
                # Tenta chaves maiúsculas e minúsculas
                base_data = EMPRESAS_DATA.get(base.upper()) or EMPRESAS_DATA.get(base)
                if base_data:
                    new_name = base_data.get(str(ons))
            
            if new_name and doc.agent_name != new_name:
                print(f"   🔄 Corrigindo Doc {doc.id} (ONS {ons}): '{doc.agent_name}' -> '{new_name}'")
                doc.agent_name = new_name
                updated_count += 1
                
        if updated_count > 0:
            db.commit()
            print(f"✅ {updated_count} documentos atualizados com sucesso!")
        else:
            print("ℹ️ Todos os nomes já estão corretos.")
            
    except Exception as e:
        print(f"❌ Erro no banco de dados: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_names()
