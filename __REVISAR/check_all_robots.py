import sqlite3

conn = sqlite3.connect('d:/Workspace/Tust-AETE/sql_app.db')
cursor = conn.cursor()

cursor.execute("SELECT DISTINCT robot_type FROM robot_configs")
rows = cursor.fetchall()

print("Tipos de robôs encontrados no banco:")
for row in rows:
    print(f"- {row[0]}")

conn.close()
