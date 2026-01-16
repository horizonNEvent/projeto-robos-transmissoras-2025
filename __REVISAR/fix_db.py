import sys
import os

# Adiciona o diretório atual ao path para importar os módulos
sys.path.append(os.getcwd())

from app.backend import database, models

print("Recriando tabelas no banco de dados...")
try:
    models.Base.metadata.create_all(bind=database.engine)
    print("Sucesso! Tabelas criadas/atualizadas.")
except Exception as e:
    print(f"Erro ao criar tabelas: {e}")
