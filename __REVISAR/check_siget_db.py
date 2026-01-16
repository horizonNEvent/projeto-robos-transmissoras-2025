import sqlite3
import json

conn = sqlite3.connect('d:/Workspace/Tust-AETE/sql_app.db')
cursor = conn.cursor()

cursor.execute("SELECT id, robot_type, base, label, username, agents_json FROM robot_configs WHERE robot_type = 'siget'")
rows = cursor.fetchall()

print(f"Total de parametrizações para 'siget': {len(rows)}")
for row in rows:
    agents = json.loads(row[5]) if row[5] else {}
    print(f"ID: {row[0]} | Base: {row[2]} | Label: {row[3]} | User: {row[4]} | Qtd Agentes: {len(agents)}")

conn.close()
