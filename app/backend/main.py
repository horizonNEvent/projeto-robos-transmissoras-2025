from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from . import models, database
from .routers import robots, empresas, transmissoras, siget, ie, config, migrate, siget_public, auth

# Criação das tabelas
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="AETE Robo Runner API")

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup: Seed Data
@app.on_event("startup")
def startup_seed_data():
    from .database import SessionLocal
    import json
    import os
    from .auth_utils import get_password_hash
    
    db = SessionLocal()
    try:
        # 1. Seed Siget Public Targets
        count = db.query(models.SigetPublicTarget).count()
        if count == 0:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            json_path = os.path.join(root_dir, "Data", "siget_public_targets.json")
            if os.path.exists(json_path):
                print("Seeding Siget Public Targets from JSON...")
                with open(json_path, 'r', encoding='utf-8') as f:
                    targets = json.load(f)
                    for code, name in targets.items():
                        exists = db.query(models.SigetPublicTarget).filter_by(codigo_ons=code).first()
                        if not exists:
                            db.add(models.SigetPublicTarget(codigo_ons=code, nome=name, ativo=True))
                    db.commit()
                    print(f"Seeded {len(targets)} targets.")

        # 2. Seed Default User
        user_count = db.query(models.User).count()
        if user_count == 0:
            print("Creating default user: BRUNO")
            admin_user = models.User(
                username="BRUNO",
                hashed_password=get_password_hash("admin"),
                email="admin@aete.com.br"
            )
            db.add(admin_user)
            db.commit()

    except Exception as e:
        print(f"Startup Seed Error: {e}")
    finally:
        db.close()

# Inclusão dos Roteadores (Modularização)
app.include_router(auth.router)
app.include_router(robots.router)
app.include_router(empresas.router)
app.include_router(transmissoras.router)
app.include_router(siget.router)
app.include_router(ie.router)
app.include_router(config.router)
app.include_router(migrate.router)
app.include_router(siget_public.router)

@app.get("/")
def health_check():
    # Health Check Endpoint (Deps Fixed)
    return {"status": "online", "message": "AETE Robo Runner Backend is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
