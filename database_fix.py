from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Pega o caminho absoluto da raiz do projeto, subindo 3 níveis da pasta 'app/backend'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Garante que o banco seja pego sempre da pasta raiz
DB_PATH = os.path.join(BASE_DIR, "sql_app.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

print(f"DATABASE PATH: {DB_PATH}")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
