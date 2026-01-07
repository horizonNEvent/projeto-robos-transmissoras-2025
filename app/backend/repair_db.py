import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../sql_app.db")

def repair():
    if not os.path.exists(db_path):
        print(f"❌ Banco não encontrado em: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    columns_to_add = [
        ("schedule_time", "TEXT"),
        ("target_competence", "TEXT"),
        ("last_success_competence", "TEXT")
    ]
    
    print(f"Checking table 'robot_configs' at {db_path}...")
    
    # Pega colunas existentes
    cursor.execute("PRAGMA table_info(robot_configs)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    
    for col_name, col_type in columns_to_add:
        if col_name not in existing_cols:
            try:
                print(f"➕ Adding column {col_name}...")
                cursor.execute(f"ALTER TABLE robot_configs ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                print(f"⚠️ Error adding {col_name}: {e}")
        else:
            print(f"✅ Column {col_name} already exists.")
            
    conn.commit()

    # Reparo na tabela 'document_registry'
    print("Checking table 'document_registry'...")
    cursor.execute("PRAGMA table_info(document_registry)")
    existing_doc_cols = [col[1] for col in cursor.fetchall()]
    if "robot_config_id" not in existing_doc_cols:
        print("➕ Adding column robot_config_id to document_registry...")
        cursor.execute("ALTER TABLE document_registry ADD COLUMN robot_config_id INTEGER")
    
    conn.commit()
    conn.close()
    print("🚀 Database repair finished!")

if __name__ == "__main__":
    repair()
