from app.backend.database import engine
from app.backend import models

models.Base.metadata.create_all(bind=engine)
print("✅ Todas as tabelas foram criadas/atualizadas no sql_app.db")
