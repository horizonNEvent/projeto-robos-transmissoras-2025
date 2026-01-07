import sqlite3
import os

db_path = "sql_app.db"

if os.path.exists(db_path):
    print(f"🔧 Iniciando reparo do banco de dados: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Colunas para adicionar na tabela robot_configs
    new_columns = [
        ("schedule_time", "TEXT"),
        ("target_competence", "TEXT"),
        ("last_success_competence", "TEXT")
    ]

    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE robot_configs ADD COLUMN {col_name} {col_type}")
            print(f"✅ Coluna '{col_name}' adicionada com sucesso.")
        except sqlite3.OperationalError:
            print(f"ℹ️ Coluna '{col_name}' já existe ou tabela não encontrada.")

    conn.commit()
    conn.close()
    print("✨ Reparo concluído.")
else:
    print("❌ Arquivo sql_app.db não encontrado para reparo.")
