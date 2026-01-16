from app.backend.database import SessionLocal
from app.backend import models

def inspect_docs():
    db = SessionLocal()
    try:
        docs = db.query(models.DocumentRegistry).all()
        print(f"Total docs: {len(docs)}")
        for doc in docs:
            print(f"ID: {doc.id} | Base: '{doc.base}' | ONS: '{doc.ons_code}' | Name: '{doc.agent_name}'")
    finally:
        db.close()

if __name__ == "__main__":
    inspect_docs()
