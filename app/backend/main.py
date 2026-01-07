from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from . import models, database
from .routers import robots, empresas, transmissoras, siget, ie, config, migrate, siget_public

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

# Startup: Init Scheduler
@app.on_event("startup")
def startup_events():
    from .scheduler import init_scheduler
    from . import models, database
    # Garante que as tabelas existam
    models.Base.metadata.create_all(bind=database.engine)
    # Init Background Scheduler
    init_scheduler()

# Inclusão dos Roteadores (Modularização)
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
    return {"status": "online", "message": "AETE Robo Runner Backend is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
